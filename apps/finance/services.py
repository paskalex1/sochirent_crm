import calendar
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Dict, List, Tuple

from django.db import transaction
from django.db.models import Q, Sum

from apps.bookings.models import Booking
from apps.owners.models import Owner
from apps.operations.models import MaintenanceTask, TaskBaseModel
from apps.properties.models import Property
from .models import Expense, FinanceRecord, OwnerReport, Payout


def get_period_bounds(year: int, month: int) -> Tuple[date, date]:
    first_day = date(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    return first_day, date(year, month, last_day)


@dataclass
class OwnerReportData:
    report: OwnerReport
    summary: Dict
    per_property: List[Dict]
    payouts: List[Dict]
    big_tasks: List[Dict]


@transaction.atomic
def generate_owner_report(owner: Owner, year: int, month: int) -> OwnerReportData:
    """
    Генерирует или обновляет OwnerReport за указанный месяц и
    возвращает агрегированные данные для API.
    """
    report, _created = OwnerReport.objects.get_or_create(
        owner=owner,
        year=year,
        month=month,
    )

    period_start, period_end = get_period_bounds(year, month)

    # Связываем FinanceRecord и Payout с отчётом.
    fin_qs = FinanceRecord.objects.filter(
        owner=owner,
        operation_date__gte=period_start,
        operation_date__lte=period_end,
    )
    fin_qs.update(owner_report=report)

    payout_qs = Payout.objects.filter(
        owner=owner,
        year=year,
        month=month,
    )
    payout_qs.update(owner_report=report)

    # Пересчитываем агрегаты по FinanceRecord.
    report.recalculate_totals()

    # Детализация по объектам.
    properties = Property.objects.filter(owner=owner)
    per_property: List[Dict] = []

    for prop in properties:
        fr_prop = fin_qs.filter(property=prop)

        income = (
            fr_prop.filter(record_type=FinanceRecord.RecordType.INCOME).aggregate(
                total=Sum("amount")
            )["total"]
            or Decimal("0.00")
        )
        expense_fr = (
            fr_prop.filter(record_type=FinanceRecord.RecordType.EXPENSE).aggregate(
                total=Sum("amount")
            )["total"]
            or Decimal("0.00")
        )

        expense_extra = (
            Expense.objects.filter(
                Q(property=prop) | Q(unit__property=prop),
                expense_date__gte=period_start,
                expense_date__lte=period_end,
            ).aggregate(total=Sum("amount"))["total"]
            or Decimal("0.00")
        )

        total_expense = expense_fr + expense_extra
        net = income - total_expense

        per_property.append(
            {
                "property_id": prop.id,
                "property_name": prop.name,
                "income_total": income,
                "expense_total": total_expense,
                "net_total": net,
            }
        )

    # Платежи владельцу за период.
    payouts_data: List[Dict] = [
        {
            "id": p.id,
            "amount": p.amount,
            "currency": p.currency,
            "status": p.status,
            "payout_date": p.payout_date,
        }
        for p in payout_qs
    ]

    # Крупные задачи MaintenanceTask с приоритетом HIGH/CRITICAL за период,
    # и расходы по ним (Expense) по property/unit и периоду.
    big_tasks_qs = MaintenanceTask.objects.filter(
        property__owner=owner,
        created_at__gte=period_start,
        created_at__lte=period_end,
        priority__in=[
            TaskBaseModel.Priority.HIGH,
            TaskBaseModel.Priority.CRITICAL,
        ],
    ).select_related("property", "unit", "executor")

    big_tasks: List[Dict] = []

    for task in big_tasks_qs:
        expenses_qs = Expense.objects.filter(
            Q(property=task.property) | Q(unit=task.unit),
            expense_date__gte=period_start,
            expense_date__lte=period_end,
        )
        expenses_data = [
            {
                "id": e.id,
                "category": e.category,
                "amount": e.amount,
                "currency": e.currency,
                "expense_date": e.expense_date,
                "contractor": e.contractor,
                "comment": e.comment,
            }
            for e in expenses_qs
        ]

        big_tasks.append(
            {
                "id": task.id,
                "title": task.title,
                "property_id": task.property_id,
                "property_name": task.property.name if task.property else None,
                "unit_id": task.unit_id,
                "priority": task.priority,
                "issue_type": task.issue_type,
                "urgency": task.urgency,
                "can_check_in": task.can_check_in,
                "created_at": task.created_at,
                "closed_at": task.closed_at,
                "executor_id": task.executor_id,
                "expenses": expenses_data,
            }
        )

    summary = {
        "income_total": report.income_total,
        "expense_total": report.expense_total,
        "net_total": report.net_total,
    }

    return OwnerReportData(
        report=report,
        summary=summary,
        per_property=per_property,
        payouts=payouts_data,
        big_tasks=big_tasks,
    )

