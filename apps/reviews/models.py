from django.db import models


class ReviewAnalysis(models.Model):
    """
    Результат AI‑анализа отзыва/жалобы гостя.
    """

    booking = models.ForeignKey(
        "bookings.Booking",
        on_delete=models.SET_NULL,
        related_name="review_analyses",
        blank=True,
        null=True,
    )
    property = models.ForeignKey(
        "properties.Property",
        on_delete=models.SET_NULL,
        related_name="review_analyses",
        blank=True,
        null=True,
    )
    unit = models.ForeignKey(
        "properties.Unit",
        on_delete=models.SET_NULL,
        related_name="review_analyses",
        blank=True,
        null=True,
    )

    source = models.CharField(
        "Источник",
        max_length=50,
        help_text="manual, ota, telegram и т.п.",
    )
    raw_text = models.TextField("Исходный текст отзыва/жалобы")

    sentiment = models.CharField(
        "Тональность",
        max_length=20,
        help_text="positive, neutral, negative",
    )
    categories = models.JSONField(
        "Категории",
        default=list,
        help_text='Например: ["cleaning", "staff", "noise"].',
    )
    summary = models.TextField("Краткое резюме")
    suggestions = models.TextField("Рекомендации", blank=True)

    created_at = models.DateTimeField("Создано", auto_now_add=True)
    analyzed_at = models.DateTimeField("Проанализировано", auto_now_add=True)

    class Meta:
        verbose_name = "AI-анализ отзыва"
        verbose_name_plural = "AI-анализы отзывов"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"ReviewAnalysis #{self.id} ({self.sentiment})"

