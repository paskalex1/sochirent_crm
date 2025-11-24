from django.db import models


class Owner(models.Model):
    """
    Собственник объекта недвижимости.
    Один владелец может иметь несколько объектов (Property).
    """

    class Status(models.TextChoices):
        ACTIVE = "active", "Активный"
        PAUSED = "paused", "На паузе"
        ARCHIVED = "archived", "Архив"

    name = models.CharField("Имя / Компания", max_length=255)
    phone = models.CharField("Телефон", max_length=32, blank=True)
    email = models.EmailField("Email", blank=True)
    notes = models.TextField("Примечания", blank=True)
    tax_id = models.CharField("ИНН / реквизиты", max_length=64, blank=True)
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
        verbose_name = "Собственник"
        verbose_name_plural = "Собственники"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

