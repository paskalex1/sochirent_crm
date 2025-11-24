from django.conf import settings
from django.contrib.auth.models import Group
from django.db import models

from apps.properties.models import Property


class Staff(models.Model):
    """
    Модель сотрудника компании Sochi.Rent.
    Связана с пользователем Django и ролями через группы.
    """

    class Role(models.TextChoices):
        CEO = "CEO", "CEO"
        COO = "COO", "COO"
        CFO = "CFO", "CFO"
        CBDO = "CBDO", "CBDO"
        HOTEL_DIRECTOR = "HotelDirector", "Hotel Director"
        GM = "GM", "General Manager"
        FRONT_DESK = "FrontDesk", "Front Desk"
        CLEANING = "Cleaning", "Cleaning"
        MAINTENANCE = "Maintenance", "Maintenance"
        QUALITY = "Quality", "Quality"
        MARKETING = "Marketing", "Marketing"
        FINANCE = "Finance", "Finance"
        IT = "IT", "IT"
        HR = "HR", "HR"

    class Department(models.TextChoices):
        PROPERTY_MANAGEMENT = "property_management", "Property management"
        HOTEL_MANAGEMENT = "hotel_management", "Hotel management"
        CLEANING = "cleaning", "Cleaning"
        MAINTENANCE = "maintenance", "Maintenance"
        FINANCE = "finance", "Finance"
        MARKETING = "marketing", "Marketing"
        IT = "it", "IT"
        HR = "hr", "HR"
        OTHER = "other", "Другое"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="staff_profile",
        verbose_name="Пользователь",
    )
    full_name = models.CharField("ФИО", max_length=255)
    position = models.CharField("Должность", max_length=255, blank=True)
    department = models.CharField(
        "Подразделение",
        max_length=50,
        choices=Department.choices,
        default=Department.OTHER,
    )
    role = models.CharField(
        "Роль",
        max_length=50,
        choices=Role.choices,
    )
    phone = models.CharField("Телефон", max_length=32, blank=True)
    email = models.EmailField("Рабочий email", blank=True)
    is_active_employee = models.BooleanField("Активен", default=True)

    properties = models.ManyToManyField(
        Property,
        related_name="staff_members",
        verbose_name="Закреплённые объекты",
        blank=True,
        help_text="Например, GM закреплён за конкретным отелем.",
    )

    schedule = models.TextField("График работы", blank=True)
    access_notes = models.TextField(
        "Права доступа (описание)",
        blank=True,
        help_text="Текстовое описание особенностей доступа. Сами права настраиваются через группы.",
    )

    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    class Meta:
        verbose_name = "Сотрудник"
        verbose_name_plural = "Сотрудники"
        ordering = ["full_name"]

    def __str__(self) -> str:
        return self.full_name or str(self.user)

    def _sync_role_group(self, old_role: str | None) -> None:
        """
        Создаёт/обновляет связь пользователя с группой согласно роли.
        Старую группу (old_role) удаляет из membership, если она отличается.
        Набор прав для группы настраивается вручную через админку.
        """

        if not self.user_id or not self.role:
            return

        # Удаляем старую роль-группу, если изменилась.
        if old_role and old_role != self.role:
            try:
                old_group = Group.objects.get(name=old_role)
            except Group.DoesNotExist:
                old_group = None
            if old_group is not None:
                self.user.groups.remove(old_group)

        # Назначаем новую группу по роли.
        group, _created = Group.objects.get_or_create(name=self.role)
        self.user.groups.add(group)

    def save(self, *args, **kwargs):
        old_role = None
        if self.pk:
            try:
                old = Staff.objects.get(pk=self.pk)
                old_role = old.role
            except Staff.DoesNotExist:
                old_role = None

        super().save(*args, **kwargs)
        self._sync_role_group(old_role)

