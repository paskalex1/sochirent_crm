from decimal import Decimal

from django.db import models
from django.db.models import Sum
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.bookings.models import Booking
from apps.owners.models import Owner
from apps.properties.models import Property, Unit


class FinanceRecord(models.Model):
    """
    Финансовая запись, связанная с бронированием / объектом / собственником.
    """

    class RecordType(models.TextChoices):
        INCOME = "income", "Доход"
        EXPENSE = "expense", "Расход"
        ADJUSTMENT = "adjustment", "Корректировка"

    booking = models.ForeignKey(
        Booking,
        on_delete=models.SET_NULL,
        related_name="finance_records",
        verbose_name="Бронирование",
        blank=True,
        null=True,
    )
    property = models.ForeignKey(
        Property,
        on_delete=models.SET_NULL,
        related_name="finance_records",
        verbose_name="Объект",
        blank=True,
        null=True,
    )
    owner = models.ForeignKey(
        Owner,
        on_delete=models.SET_NULL,
        related_name="finance_records",
        verbose_name="Собственник",
        blank=True,
        null=True,
    )
    owner_report = models.ForeignKey(
        "OwnerReport",
        on_delete=models.SET_NULL,
        related_name="finance_records",
        verbose_name="Отчёт собственнику",
        blank=True,
        null=True,
    )
    record_type = models.CharField(
        "Тип записи",
        max_length=20,
        choices=RecordType.choices,
    )
    category = models.CharField(
        "Категория",
        max_length=100,
        help_text="Например: аренда, уборка, ремонт, комиссия OTA и т.п.",
    )
    amount = models.DecimalField("Сумма", max_digits=12, decimal_places=2)
    currency = models.CharField("Валюта", max_length=10, default="RUB")
    operation_date = models.DateField("Дата операции")
    comment = models.TextField("Комментарий", blank=True)
    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Финансовая запись"
        verbose_name_plural = "Финансовые записи"
        ordering = ["-operation_date", "-id"]

    def __str__(self) -> str:
        return f"{self.get_record_type_display()} {self.amount} {self.currency}"


class Expense(models.Model):
    """
    Расход по объекту / юниту.
    """

    property = models.ForeignKey(
        Property,
        on_delete=models.SET_NULL,
        related_name="expenses",
        verbose_name="Объект",
        blank=True,
        null=True,
    )
    unit = models.ForeignKey(
        Unit,
        on_delete=models.SET_NULL,
        related_name="expenses",
        verbose_name="Юнит",
        blank=True,
        null=True,
    )
    category = models.CharField("Категория расхода", max_length=100)
    amount = models.DecimalField("Сумма", max_digits=12, decimal_places=2)
    currency = models.CharField("Валюта", max_length=10, default="RUB")
    expense_date = models.DateField("Дата расхода")
    contractor = models.CharField(
        "Подрядчик / контрагент",
        max_length=255,
        blank=True,
        help_text="Название подрядчика, если есть.",
    )
    comment = models.TextField("Комментарий", blank=True)
    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Расход"
        verbose_name_plural = "Расходы"
        ordering = ["-expense_date", "-id"]

    def clean(self):
        super().clean()
        if not self.property and not self.unit:
            raise ValidationError(
                "Необходимо указать либо объект (Property), либо юнит (Unit) для расхода."
            )

    def __str__(self) -> str:
        target = self.property or self.unit
        return f"Расход {self.amount} {self.currency} — {target}"


class OwnerReport(models.Model):
    """
    Агрегированный отчёт для собственника за период (месяц/год).
    """

    owner = models.ForeignKey(
        Owner,
        on_delete=models.CASCADE,
        related_name="owner_reports",
        verbose_name="Собственник",
    )
    year = models.PositiveIntegerField("Год")
    month = models.PositiveSmallIntegerField("Месяц")

    income_total = models.DecimalField(
        "Сумма доходов",
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    expense_total = models.DecimalField(
        "Сумма расходов",
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    net_total = models.DecimalField(
        "Чистая прибыль",
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    is_sent = models.BooleanField(
        "Отправлен собственнику",
        default=False,
    )
    sent_at = models.DateTimeField(
        "Дата отправки",
        blank=True,
        null=True,
    )
    is_signed = models.BooleanField(
        "Подписан собственником",
        default=False,
    )
    signed_at = models.DateTimeField(
        "Дата подписания",
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    class Meta:
        verbose_name = "Отчёт собственнику"
        verbose_name_plural = "Отчёты собственникам"
        unique_together = ("owner", "year", "month")
        ordering = ["-year", "-month", "owner"]

    def __str__(self) -> str:
        return f"Отчёт {self.owner} за {self.month:02d}.{self.year}"

    def recalculate_totals(self) -> None:
        """
        Пересчитывает агрегированные суммы на основе связанных FinanceRecord.

        Корректировки (type=adjustment) пока в агрегацию не входят.
        """
        qs = self.finance_records.all()
        income_sum = (
            qs.filter(record_type=FinanceRecord.RecordType.INCOME).aggregate(
                total=Sum("amount")
            )["total"]
            or Decimal("0.00")
        )
        expense_sum = (
            qs.filter(record_type=FinanceRecord.RecordType.EXPENSE).aggregate(
                total=Sum("amount")
            )["total"]
            or Decimal("0.00")
        )
        self.income_total = income_sum
        self.expense_total = expense_sum
        self.net_total = income_sum - expense_sum
        self.save(update_fields=["income_total", "expense_total", "net_total", "updated_at"])

    def save(self, *args, **kwargs):
        if self.pk:
            try:
                old = OwnerReport.objects.get(pk=self.pk)
            except OwnerReport.DoesNotExist:
                old = None
        else:
            old = None

        now = timezone.now()

        if self.is_sent and self.sent_at is None:
            if not old or not old.is_sent:
                self.sent_at = now

        if self.is_signed and self.signed_at is None:
            if not old or not old.is_signed:
                self.signed_at = now

        super().save(*args, **kwargs)


class Payout(models.Model):
    """
    Выплата собственнику за период.
    """

    class Status(models.TextChoices):
        PLANNED = "planned", "Запланирована"
        PAID = "paid", "Выплачена"

    owner = models.ForeignKey(
        Owner,
        on_delete=models.CASCADE,
        related_name="payouts",
        verbose_name="Собственник",
    )
    owner_report = models.ForeignKey(
        OwnerReport,
        on_delete=models.SET_NULL,
        related_name="payouts",
        verbose_name="Отчёт собственнику",
        blank=True,
        null=True,
    )
    year = models.PositiveIntegerField("Год")
    month = models.PositiveSmallIntegerField("Месяц")
    amount = models.DecimalField("Сумма к выплате", max_digits=12, decimal_places=2)
    currency = models.CharField("Валюта", max_length=10, default="RUB")
    status = models.CharField(
        "Статус",
        max_length=20,
        choices=Status.choices,
        default=Status.PLANNED,
    )
    payout_date = models.DateField("Дата выплаты", blank=True, null=True)
    comment = models.TextField("Комментарий", blank=True)
    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Выплата собственнику"
        verbose_name_plural = "Выплаты собственникам"
        unique_together = ("owner", "year", "month")
        ordering = ["-year", "-month", "owner"]

    def __str__(self) -> str:
        return f"Выплата {self.owner} за {self.month:02d}.{self.year}"
