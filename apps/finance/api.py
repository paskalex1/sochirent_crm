from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.owners.models import Owner
from apps.staff.permissions import IsFinanceRole, IsFinanceSummaryRole
from .models import Expense, FinanceRecord, OwnerReport, Payout
from .services import generate_owner_report


class FinanceRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = FinanceRecord
        fields = [
            "id",
            "booking",
            "property",
            "owner",
            "owner_report",
            "record_type",
            "category",
            "amount",
            "currency",
            "operation_date",
            "comment",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ExpenseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Expense
        fields = [
            "id",
            "property",
            "unit",
            "category",
            "amount",
            "currency",
            "expense_date",
            "contractor",
            "comment",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class PayoutSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payout
        fields = [
            "id",
            "owner",
            "owner_report",
            "year",
            "month",
            "amount",
            "currency",
            "status",
            "payout_date",
            "comment",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class OwnerReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = OwnerReport
        fields = [
            "id",
            "owner",
            "year",
            "month",
            "income_total",
            "expense_total",
            "net_total",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "income_total",
            "expense_total",
            "net_total",
            "created_at",
            "updated_at",
        ]


class FinanceRecordViewSet(viewsets.ModelViewSet):
    queryset = FinanceRecord.objects.select_related(
        "booking", "property", "owner", "owner_report"
    ).all()
    serializer_class = FinanceRecordSerializer
    permission_classes = [IsFinanceRole]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = [
        "record_type",
        "category",
        "currency",
        "operation_date",
        "property",
        "owner",
        "booking",
        "owner_report",
    ]


class ExpenseViewSet(viewsets.ModelViewSet):
    queryset = Expense.objects.select_related("property", "unit").all()
    serializer_class = ExpenseSerializer
    permission_classes = [IsFinanceRole]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = [
        "category",
        "currency",
        "expense_date",
        "property",
        "unit",
    ]


class PayoutViewSet(viewsets.ModelViewSet):
    queryset = Payout.objects.select_related("owner", "owner_report").all()
    serializer_class = PayoutSerializer
    permission_classes = [IsFinanceRole]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = [
        "owner",
        "year",
        "month",
        "status",
    ]


class OwnerReportViewSet(viewsets.ModelViewSet):
    queryset = OwnerReport.objects.select_related("owner").all()
    serializer_class = OwnerReportSerializer
    permission_classes = [IsFinanceRole]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = [
        "owner",
        "year",
        "month",
    ]

    @action(detail=False, methods=["post"], url_path="generate")
    def generate(self, request, *args, **kwargs):
        """
        Генерирует отчёт OwnerReport за указанный месяц и возвращает
        агрегированную структуру:
          - summary (доходы/расходы/чистая прибыль),
          - детализация по объектам,
          - выплаты,
          - список крупных задач с расходами по ним.

        Ожидает в теле запроса:
          - owner (int, id собственника),
          - year (int),
          - month (int, 1–12).
        """
        owner_id = request.data.get("owner")
        year = request.data.get("year")
        month = request.data.get("month")

        if not owner_id or not year or not month:
            return Response(
                {"detail": "Поля 'owner', 'year', 'month' обязательны."},
                status=400,
            )

        owner = get_object_or_404(Owner, pk=owner_id)

        try:
            year_int = int(year)
            month_int = int(month)
        except (TypeError, ValueError):
            return Response(
                {"detail": "Поля 'year' и 'month' должны быть целыми числами."},
                status=400,
            )

        if month_int < 1 or month_int > 12:
            return Response(
                {"detail": "Поле 'month' должно быть в диапазоне 1–12."},
                status=400,
            )

        data = generate_owner_report(owner, year_int, month_int)
        report_data = OwnerReportSerializer(data.report).data

        return Response(
            {
                "owner_report": report_data,
                "summary": data.summary,
                "per_property": data.per_property,
                "payouts": data.payouts,
                "big_maintenance_tasks": data.big_tasks,
            }
        )


class FinanceSummaryView(APIView):
    """
    Агрегированное финансовое summary по периодам.

    Доступно для управленческих/маркетинговых ролей (IsFinanceSummaryRole),
    без детализации по отдельным операциям.

    Поддерживаются query-параметры:
      - year (int)
      - month (int, 1–12)
    Если параметры не заданы, считается агрегат по всем записям.
    """

    permission_classes = [IsFinanceSummaryRole]

    def get(self, request, *args, **kwargs):
        qs = FinanceRecord.objects.all()

        year = request.query_params.get("year")
        month = request.query_params.get("month")

        if year:
            qs = qs.filter(operation_date__year=year)
        if month:
            qs = qs.filter(operation_date__month=month)

        # Агрегируем по валюте, чтобы не смешивать разные валюты.
        data = []
        for row in (
            qs.values("currency")
            .annotate(
                income_total=Sum(
                    "amount", filter=Q(record_type=FinanceRecord.RecordType.INCOME)
                ),
                expense_total=Sum(
                    "amount", filter=Q(record_type=FinanceRecord.RecordType.EXPENSE)
                ),
            )
            .order_by("currency")
        ):
            income = row["income_total"] or 0
            expense = row["expense_total"] or 0
            net = income - expense
            data.append(
                {
                    "currency": row["currency"],
                    "income_total": income,
                    "expense_total": expense,
                    "net_total": net,
                }
            )

        return Response(
            {
                "period": {
                    "year": int(year) if year is not None else None,
                    "month": int(month) if month is not None else None,
                },
                "summary": data,
            }
        )
