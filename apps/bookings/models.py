from django.conf import settings
from django.db import models

from apps.owners.models import Owner
from apps.properties.models import Property, Unit


class Guest(models.Model):
    """
    Гость / арендатор.
    """

    full_name = models.CharField("ФИО", max_length=255)
    phone = models.CharField("Телефон", max_length=32, blank=True)
    email = models.EmailField("Email", blank=True)
    document_type = models.CharField("Тип документа", max_length=50, blank=True)
    document_number = models.CharField("Номер документа", max_length=50, blank=True)
    country = models.CharField("Страна", max_length=100, blank=True)
    city = models.CharField("Город", max_length=100, blank=True)
    notes = models.TextField("Заметки", blank=True)
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    class Meta:
        verbose_name = "Гость"
        verbose_name_plural = "Гости"
        ordering = ["full_name"]

    def __str__(self) -> str:
        return self.full_name


class RatePlan(models.Model):
    """
    Тарифный план / ценовая стратегия для объекта (Property).

    В рамках A2 привязан только к Property.
    """

    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="rate_plans",
        verbose_name="Объект",
    )
    name = models.CharField("Название тарифа", max_length=255)
    description = models.TextField("Описание", blank=True)
    base_price = models.DecimalField(
        "Базовая цена",
        max_digits=10,
        decimal_places=2,
    )
    params = models.JSONField(
        "Параметры тарифа",
        default=dict,
        blank=True,
        help_text="Произвольные параметры тарифного плана в формате JSON.",
    )
    is_active = models.BooleanField("Активен", default=True)
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    class Meta:
        verbose_name = "Тарифный план"
        verbose_name_plural = "Тарифные планы"
        ordering = ["property", "name"]

    def __str__(self) -> str:
        return f"{self.property.name} — {self.name}"


class Booking(models.Model):
    """
    Бронирование (краткосрочное, долгосрочное, отельное).
    """

    class Status(models.TextChoices):
        NEW = "new", "Новая"
        CONFIRMED = "confirmed", "Подтверждена"
        CHECKIN = "checkin", "Заезд"
        CHECKOUT = "checkout", "Выезд"
        CANCELED = "canceled", "Отменена"
        NO_SHOW = "no_show", "No-show"

    class Source(models.TextChoices):
        OTA = "ota", "OTA"
        DIRECT = "direct", "Прямой"
        CORPORATE = "corporate", "Корпоративный"
        LONG_TERM = "long_term", "Долгосрочный"

    unit = models.ForeignKey(
        Unit,
        on_delete=models.PROTECT,
        related_name="bookings",
        verbose_name="Юнит",
    )
    property = models.ForeignKey(
        Property,
        on_delete=models.PROTECT,
        related_name="bookings",
        verbose_name="Объект",
    )
    guest = models.ForeignKey(
        Guest,
        on_delete=models.PROTECT,
        related_name="bookings",
        verbose_name="Гость",
    )
    rate_plan = models.ForeignKey(
        RatePlan,
        on_delete=models.SET_NULL,
        related_name="bookings",
        verbose_name="Тарифный план",
        blank=True,
        null=True,
    )
    owner = models.ForeignKey(
        Owner,
        on_delete=models.SET_NULL,
        related_name="bookings",
        verbose_name="Собственник",
        blank=True,
        null=True,
    )
    check_in = models.DateField("Дата заезда")
    check_out = models.DateField("Дата выезда")
    status = models.CharField(
        "Статус",
        max_length=20,
        choices=Status.choices,
        default=Status.NEW,
    )
    source = models.CharField(
        "Источник",
        max_length=20,
        choices=Source.choices,
        default=Source.DIRECT,
    )
    amount = models.DecimalField("Сумма", max_digits=10, decimal_places=2)
    currency = models.CharField("Валюта", max_length=10, default="RUB")
    prepayment_amount = models.DecimalField(
        "Предоплата",
        max_digits=10,
        decimal_places=2,
        default=0,
    )
    payment_status = models.CharField(
        "Статус платежа",
        max_length=50,
        blank=True,
        help_text="Упрощённое текстовое поле для статуса платежа.",
    )
    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Бронирование"
        verbose_name_plural = "Бронирования"
        ordering = ["-check_in", "-id"]

    def __str__(self) -> str:
        return f"Бронь #{self.id} — {self.guest.full_name}"


class CalendarEvent(models.Model):
    """
    Событие календаря занятости юнита.
    """

    unit = models.ForeignKey(
        Unit,
        on_delete=models.CASCADE,
        related_name="calendar_events",
        verbose_name="Юнит",
    )
    booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        related_name="calendar_events",
        verbose_name="Бронирование",
        blank=True,
        null=True,
    )
    event_type = models.CharField(
        "Тип события",
        max_length=50,
        help_text="Например: booking, maintenance_block, owner_block и т.п.",
    )
    start_date = models.DateField("Дата начала")
    end_date = models.DateField("Дата окончания")
    note = models.TextField("Примечание", blank=True)
    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Событие календаря"
        verbose_name_plural = "События календаря"
        ordering = ["unit", "start_date"]

    def __str__(self) -> str:
        return f"{self.unit} — {self.event_type} ({self.start_date}–{self.end_date})"


class BookingStatusLog(models.Model):
    """
    История изменений статуса бронирования.
    """

    booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        related_name="status_logs",
        verbose_name="Бронирование",
    )
    old_status = models.CharField("Старый статус", max_length=20, blank=True)
    new_status = models.CharField("Новый статус", max_length=20)
    changed_at = models.DateTimeField("Изменено", auto_now_add=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="booking_status_changes",
        verbose_name="Изменил",
        blank=True,
        null=True,
    )

    class Meta:
        verbose_name = "Изменение статуса брони"
        verbose_name_plural = "Изменения статусов броней"
        ordering = ["-changed_at"]

    def __str__(self) -> str:
        return f"Бронь #{self.booking_id}: {self.old_status} → {self.new_status}"
