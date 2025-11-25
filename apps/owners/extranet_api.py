import calendar
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List

from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.bookings.models import Booking
from apps.finance.api import OwnerReportSerializer
from apps.finance.models import OwnerReport
from apps.finance.services import generate_owner_report, get_period_bounds
from apps.owners.api import OwnerSerializer
from apps.owners.models import Owner
from apps.properties.api import calculate_hotel_stats
from apps.properties.models import Property, Unit


def _calculate_non_hotel_occupancy(prop: Property, year: int, month: int) -> Dict[str, Any]:
    """
    Расчёт средней занятости для объектов, отличных от hotel.

    Формула:
      occupancy_avg = occupied_nights / (units_count * days_in_period)
    где:
      - occupied_nights — суммарное количество занятых ночей по всем бронированиям,
      - units_count — количество активных юнитов объекта,
      - days_in_period — количество дней в выбранном месяце.
    """
    period_start, period_end = get_period_bounds(year, month)
    days_in_period = (period_end - period_start).days + 1

    units_count = prop.units.filter(
        status=Unit.Status.ACTIVE,
        is_active=True,
    ).count()

    if units_count == 0 or days_in_period <= 0:
        return {
            "type": prop.type,
            "occupancy_avg": None,
        }

    bookings_qs = Booking.objects.filter(
        property=prop,
        check_in__lt=period_end,
        check_out__gt=period_start,
    )

    occupied_nights = 0
    for booking in bookings_qs:
        start = max(booking.check_in, period_start)
        end = min(booking.check_out, period_end + timezone.timedelta(days=1))
        nights = (end - start).days
        if nights > 0:
            occupied_nights += nights

    denominator = units_count * days_in_period
    if denominator <= 0:
        occupancy_avg = None
    else:
        occupancy_avg = occupied_nights / denominator

    return {
        "type": prop.type,
        "occupancy_avg": float(occupancy_avg) if occupancy_avg is not None else None,
    }


class OwnerDashboardView(APIView):
    """
    Дашборд собственника (Extranet).

    URL:
      GET /api/v1/extranet/owner/dashboard/?year=&month=

    Доступен только пользователям, у которых есть request.user.owner_profile.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user
        try:
            owner: Owner = user.owner_profile  # type: ignore[attr-defined]
        except Owner.DoesNotExist:
            return Response(
                {"detail": "Доступ разрешён только собственникам."},
                status=403,
            )
        except AttributeError:
            return Response(
                {"detail": "Доступ разрешён только собственникам."},
                status=403,
            )

        now = timezone.now().date()
        try:
            year = int(request.query_params.get("year", now.year))
        except (TypeError, ValueError):
            year = now.year
        try:
            month = int(request.query_params.get("month", now.month))
        except (TypeError, ValueError):
            month = now.month

        month = max(1, min(12, month))

        report_data = generate_owner_report(owner, year, month)

        # Карта финансов по объектам: property_id -> finance dict.
        per_property_finance: Dict[int, Dict[str, float]] = {}
        for item in report_data.per_property:
            prop_id = int(item["property_id"])
            income = item["income_total"]
            expense = item["expense_total"]
            net = item["net_total"]
            per_property_finance[prop_id] = {
                "income_total": float(income) if isinstance(income, Decimal) else income,
                "expense_total": float(expense) if isinstance(expense, Decimal) else expense,
                "net_total": float(net) if isinstance(net, Decimal) else net,
            }

        properties_qs = Property.objects.filter(owner=owner).select_related("owner", "manager")

        properties_data: List[Dict[str, Any]] = []
        for prop in properties_qs:
            if prop.type == Property.PropertyType.HOTEL:
                hotel_stats = calculate_hotel_stats(prop, year, month)
                summary = hotel_stats.get("summary", {})
                stats_payload: Dict[str, Any] = {
                    "type": prop.type,
                    "occupancy_avg": summary.get("occupancy_avg"),
                    "adr_avg": summary.get("adr_avg"),
                    "revpar_avg": summary.get("revpar_avg"),
                }
            else:
                stats_payload = _calculate_non_hotel_occupancy(prop, year, month)

            finance_payload = per_property_finance.get(
                prop.id,
                {
                    "income_total": 0.0,
                    "expense_total": 0.0,
                    "net_total": 0.0,
                },
            )

            properties_data.append(
                {
                    "property": {
                        "id": prop.id,
                        "name": prop.name,
                        "type": prop.type,
                        "city": prop.city,
                        "district": prop.district,
                        "address": prop.address,
                        "status": prop.status,
                    },
                    "finance": finance_payload,
                    "stats": stats_payload,
                }
            )

        # Суммарные финпоказатели по Owner за период.
        summary = {
            "income_total": float(report_data.summary["income_total"])
            if isinstance(report_data.summary["income_total"], Decimal)
            else report_data.summary["income_total"],
            "expense_total": float(report_data.summary["expense_total"])
            if isinstance(report_data.summary["expense_total"], Decimal)
            else report_data.summary["expense_total"],
            "net_income": float(report_data.summary["net_total"])
            if isinstance(report_data.summary["net_total"], Decimal)
            else report_data.summary["net_total"],
        }

        # Крупные задачи по эксплуатации за период.
        big_tasks: List[Dict[str, Any]] = []
        for task in report_data.big_tasks:
            expenses: List[Dict[str, Any]] = []
            for e in task.get("expenses", []):
                amount = e["amount"]
                expenses.append(
                    {
                        "id": e["id"],
                        "category": e["category"],
                        "amount": float(amount) if isinstance(amount, Decimal) else amount,
                        "currency": e["currency"],
                        "expense_date": e["expense_date"],
                        "contractor": e["contractor"],
                        "comment": e["comment"],
                    }
                )

            big_tasks.append(
                {
                    "id": task["id"],
                    "title": task["title"],
                    "property_id": task["property_id"],
                    "property_name": task["property_name"],
                    "unit_id": task["unit_id"],
                    "priority": task["priority"],
                    "issue_type": task["issue_type"],
                    "urgency": task["urgency"],
                    "can_check_in": task["can_check_in"],
                    "created_at": task["created_at"],
                    "closed_at": task["closed_at"],
                    "executor_id": task["executor_id"],
                    "expenses": expenses,
                }
            )

        owner_data_full = OwnerSerializer(owner).data
        owner_data = {
            "id": owner_data_full.get("id"),
            "name": owner_data_full.get("name"),
            "phone": owner_data_full.get("phone"),
            "email": owner_data_full.get("email"),
        }

        return Response(
            {
                "owner": owner_data,
                "period": {"year": year, "month": month},
                "summary": summary,
                "properties": properties_data,
                "big_tasks": big_tasks,
            }
        )


class OwnerReportsView(APIView):
    """
    Список отчётов OwnerReport для текущего собственника.

    URL:
      GET /api/v1/extranet/owner/reports/?year=&month=
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user
        try:
            owner: Owner = user.owner_profile  # type: ignore[attr-defined]
        except Owner.DoesNotExist:
            return Response(
                {"detail": "Доступ разрешён только собственникам."},
                status=403,
            )
        except AttributeError:
            return Response(
                {"detail": "Доступ разрешён только собственникам."},
                status=403,
            )

        qs = OwnerReport.objects.filter(owner=owner).order_by("-year", "-month")

        year = request.query_params.get("year")
        month = request.query_params.get("month")

        if year:
            try:
                year_int = int(year)
                qs = qs.filter(year=year_int)
            except (TypeError, ValueError):
                pass
        if month:
            try:
                month_int = int(month)
                if 1 <= month_int <= 12:
                    qs = qs.filter(month=month_int)
            except (TypeError, ValueError):
                pass

        serializer = OwnerReportSerializer(qs, many=True)
        return Response(serializer.data)
