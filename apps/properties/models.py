from django.conf import settings
from django.db import models

from apps.owners.models import Owner


class Property(models.Model):
    """
    Объект недвижимости (жилой, коммерческий, отель).
    Один объект может содержать несколько юнитов (Unit).
    """

    class PropertyType(models.TextChoices):
        RESIDENTIAL_SHORT = "residential_short", "Жилая (посуточно)"
        RESIDENTIAL_LONG = "residential_long", "Жилая (долгосрочно)"
        COMMERCIAL = "commercial", "Коммерческая"
        HOTEL = "hotel", "Отель / апарт-отель"

    class Status(models.TextChoices):
        IN_MANAGEMENT = "in_management", "В управлении"
        ONBOARDING = "onboarding", "На подключении"
        ARCHIVED = "archived", "Архив"

    owner = models.ForeignKey(
        Owner,
        on_delete=models.CASCADE,
        related_name="properties",
        verbose_name="Собственник",
    )
    type = models.CharField(
        "Тип объекта",
        max_length=32,
        choices=PropertyType.choices,
    )
    name = models.CharField("Название объекта", max_length=255)
    city = models.CharField("Город", max_length=100)
    district = models.CharField("Район", max_length=100, blank=True)
    address = models.CharField("Адрес", max_length=255)
    status = models.CharField(
        "Статус",
        max_length=20,
        choices=Status.choices,
        default=Status.IN_MANAGEMENT,
    )
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="managed_properties",
        verbose_name="Ответственный менеджер",
        blank=True,
        null=True,
    )
    is_active = models.BooleanField("Активен", default=True)
    hotel_star_rating = models.PositiveSmallIntegerField(
        "Звёздность отеля",
        blank=True,
        null=True,
        help_text="Для hotel-объектов: количество звёзд (1–5).",
    )
    has_reception = models.BooleanField(
        "Есть ресепшен",
        default=False,
        help_text="Применимо для объектов типа 'hotel'.",
    )
    rooms_count = models.PositiveIntegerField(
        "Количество номеров",
        blank=True,
        null=True,
        help_text="Ориентировочное количество номеров (может отличаться от числа юнитов).",
    )
    checkin_time = models.TimeField(
        "Время заезда",
        blank=True,
        null=True,
        help_text="Применимо для объектов типа 'hotel'.",
    )
    checkout_time = models.TimeField(
        "Время выезда",
        blank=True,
        null=True,
        help_text="Применимо для объектов типа 'hotel'.",
    )
    brand_name = models.CharField(
        "Бренд / сеть",
        max_length=255,
        blank=True,
        help_text="Если отель работает под брендом/сетью.",
    )
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    class Meta:
        verbose_name = "Объект недвижимости"
        verbose_name_plural = "Объекты недвижимости"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Unit(models.Model):
    """
    Юнит размещения (номер, апартамент, коммерческая единица).
    """

    class UnitType(models.TextChoices):
        ROOM = "room", "Номер"
        APARTMENT = "apartment", "Апартамент"
        COMMERCIAL_UNIT = "commercial_unit", "Коммерческая единица"

    class Status(models.TextChoices):
        ACTIVE = "active", "Активен"
        MAINTENANCE = "maintenance", "На ремонте"
        BLOCKED = "blocked", "Заблокирован"

    room_type = models.ForeignKey(
        "RoomType",
        on_delete=models.SET_NULL,
        related_name="units",
        verbose_name="Тип номера",
        blank=True,
        null=True,
    )
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="units",
        verbose_name="Объект",
    )
    type = models.CharField(
        "Тип юнита",
        max_length=32,
        choices=UnitType.choices,
    )
    code = models.CharField("Код / Название", max_length=100)
    description = models.TextField("Описание", blank=True)
    floor = models.IntegerField("Этаж", blank=True, null=True)
    area = models.DecimalField("Метраж, м²", max_digits=7, decimal_places=2, blank=True, null=True)
    capacity = models.PositiveIntegerField("Вместимость", blank=True, null=True)
    status = models.CharField(
        "Статус",
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    is_active = models.BooleanField("Активен", default=True)
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    class Meta:
        verbose_name = "Юнит"
        verbose_name_plural = "Юниты"
        ordering = ["property", "code"]
        unique_together = ("property", "code")

    def __str__(self) -> str:
        return f"{self.property.name} — {self.code}"


class UnitPhoto(models.Model):
    """
    Фото юнита.
    """

    unit = models.ForeignKey(
        Unit,
        on_delete=models.CASCADE,
        related_name="photos",
        verbose_name="Юнит",
    )
    image = models.FileField("Фото", upload_to="unit_photos/")
    caption = models.CharField("Подпись", max_length=255, blank=True)
    created_at = models.DateTimeField("Загружено", auto_now_add=True)

    class Meta:
        verbose_name = "Фото юнита"
        verbose_name_plural = "Фото юнитов"

    def __str__(self) -> str:
        return f"Фото {self.unit} ({self.id})"


class RoomType(models.Model):
    """
    Тип номера (категория) для hotel-объектов.
    """

    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="room_types",
        verbose_name="Отель",
    )
    name = models.CharField("Название категории", max_length=255)
    base_capacity = models.PositiveIntegerField(
        "Базовая вместимость",
        help_text="Количество гостей по умолчанию.",
    )
    base_area = models.DecimalField(
        "Средняя площадь, м²",
        max_digits=7,
        decimal_places=2,
        blank=True,
        null=True,
    )
    amenities = models.TextField(
        "Удобства",
        blank=True,
        help_text="Описание основных удобств и особенностей категории.",
    )
    is_active = models.BooleanField("Активен", default=True)

    class Meta:
        verbose_name = "Тип номера"
        verbose_name_plural = "Типы номеров"
        ordering = ["property", "name"]

    def __str__(self) -> str:
        return f"{self.property.name} — {self.name}"
