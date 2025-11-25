from decimal import Decimal

from django.db import models


class PriceRecommendation(models.Model):
    """
    Лог рекомендации цены для юнита на конкретную дату.
    """

    unit = models.ForeignKey(
        "properties.Unit",
        on_delete=models.CASCADE,
        related_name="price_recommendations",
        verbose_name="Юнит",
    )
    date = models.DateField("Дата")

    base_price = models.DecimalField("Базовая цена", max_digits=10, decimal_places=2)
    recommended_price = models.DecimalField(
        "Рекомендованная цена",
        max_digits=10,
        decimal_places=2,
    )
    min_price = models.DecimalField("Минимальная цена", max_digits=10, decimal_places=2)
    max_price = models.DecimalField("Максимальная цена", max_digits=10, decimal_places=2)

    occupancy_7d = models.FloatField("Загрузка за 7 дней", null=True, blank=True)
    occupancy_30d = models.FloatField("Загрузка за 30 дней", null=True, blank=True)
    season = models.CharField(
        "Сезон",
        max_length=20,
        blank=True,
        help_text="low, shoulder, high",
    )

    notes = models.TextField("Примечание", blank=True)

    created_at = models.DateTimeField("Создано", auto_now_add=True)

    class Meta:
        verbose_name = "Рекомендация цены"
        verbose_name_plural = "Рекомендации цен"
        ordering = ["-date", "-created_at"]

    def __str__(self) -> str:
        return f"{self.unit} @ {self.date}: {self.recommended_price}"

