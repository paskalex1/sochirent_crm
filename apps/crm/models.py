from django.db import models
from django.conf import settings

class Pipeline(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, unique=True)
    is_active = models.BooleanField(default=True)
    def __str__(self): return self.name

class Stage(models.Model):
    pipeline = models.ForeignKey(Pipeline, on_delete=models.CASCADE, related_name="stages")
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50)
    order = models.PositiveIntegerField(default=0)
    is_won = models.BooleanField(default=False)
    is_lost = models.BooleanField(default=False)
    class Meta:
        unique_together = ("pipeline", "code")
        ordering = ["order"]
    def __str__(self): return f"{self.pipeline.name}: {self.name}"

class Lead(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "Новый"
        IN_PROGRESS = "in_progress", "В работе"
        CONVERTED = "converted", "Конвертирован"
        DISQUALIFIED = "disqualified", "Отсеян"
    full_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=32, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    source = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    responsible = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        blank=True, null=True, related_name="leads"
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return self.full_name

class Deal(models.Model):
    title = models.CharField(max_length=255)
    lead = models.ForeignKey(Lead, on_delete=models.SET_NULL, blank=True, null=True, related_name="deals")
    pipeline = models.ForeignKey(Pipeline, on_delete=models.PROTECT, related_name="deals")
    stage = models.ForeignKey(Stage, on_delete=models.PROTECT, related_name="deals")
    value = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    responsible = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        blank=True, null=True, related_name="deals"
    )
    probability = models.PositiveIntegerField(default=0)  # 0–100
    expected_close_date = models.DateField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_closed = models.BooleanField(default=False)
    def __str__(self): return self.title
