from django.contrib import admin

from .models import Expense, FinanceRecord, OwnerReport, Payout


@admin.register(FinanceRecord)
class FinanceRecordAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "record_type",
        "category",
        "amount",
        "currency",
        "operation_date",
        "booking",
        "property",
        "owner",
        "owner_report",
    )
    list_filter = ("record_type", "category", "currency", "operation_date")
    search_fields = ("category", "comment")


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "property",
        "unit",
        "category",
        "amount",
        "currency",
        "expense_date",
        "contractor",
    )
    list_filter = ("category", "currency", "expense_date", "property")
    search_fields = ("category", "contractor", "comment")


@admin.register(OwnerReport)
class OwnerReportAdmin(admin.ModelAdmin):
    list_display = (
        "owner",
        "year",
        "month",
        "income_total",
        "expense_total",
        "net_total",
        "created_at",
    )
    list_filter = ("year", "month", "owner")
    search_fields = ("owner__name",)


@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = (
        "owner",
        "year",
        "month",
        "amount",
        "currency",
        "status",
        "payout_date",
        "owner_report",
    )
    list_filter = ("status", "year", "month", "owner")
    search_fields = ("owner__name", "comment")

