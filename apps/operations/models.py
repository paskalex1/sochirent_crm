from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone

from apps.bookings.models import Booking
from apps.owners.models import Owner
from apps.properties.models import Property, Unit


class TaskBaseModel(models.Model):
    """
    Базовая абстрактная модель задач.
    """

    class Status(models.TextChoices):
        NEW = "new", "Запланирована"
        IN_PROGRESS = "in_progress", "В работе"
        UNDER_REVIEW = "under_review", "На проверке"
        DONE = "done", "Выполнена"
        CANCELED = "canceled", "Отменена"

    class Priority(models.TextChoices):
        LOW = "low", "Низкий"
        NORMAL = "normal", "Нормальный"
        HIGH = "high", "Высокий"
        CRITICAL = "critical", "Критический"

    class TaskType(models.TextChoices):
        CLEANING = "cleaning", "Уборка"
        MAINTENANCE = "maintenance", "Эксплуатация"
        CHECKIN = "checkin", "Заселение"
        CHECKOUT = "checkout", "Выселение"
        QUALITY = "quality_inspection", "Контроль качества"
        OWNER_REQUEST = "owner_request", "Запрос собственника"

    title = models.CharField("Заголовок", max_length=255)
    description = models.TextField("Описание", blank=True)
    task_type = models.CharField(
        "Тип задачи",
        max_length=32,
        choices=TaskType.choices,
    )
    status = models.CharField(
        "Статус",
        max_length=20,
        choices=Status.choices,
        default=Status.NEW,
    )
    priority = models.CharField(
        "Приоритет",
        max_length=20,
        choices=Priority.choices,
        default=Priority.NORMAL,
    )
    executor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="%(app_label)s_%(class)s_tasks",
        verbose_name="Исполнитель",
        blank=True,
        null=True,
    )
    deadline = models.DateTimeField("Дедлайн", blank=True, null=True)

    property = models.ForeignKey(
        Property,
        on_delete=models.SET_NULL,
        related_name="%(app_label)s_%(class)s_tasks",
        verbose_name="Объект",
        blank=True,
        null=True,
    )
    unit = models.ForeignKey(
        Unit,
        on_delete=models.SET_NULL,
        related_name="%(app_label)s_%(class)s_tasks",
        verbose_name="Юнит",
        blank=True,
        null=True,
    )
    booking = models.ForeignKey(
        Booking,
        on_delete=models.SET_NULL,
        related_name="%(app_label)s_%(class)s_tasks",
        verbose_name="Бронирование",
        blank=True,
        null=True,
    )
    owner = models.ForeignKey(
        Owner,
        on_delete=models.SET_NULL,
        related_name="%(app_label)s_%(class)s_tasks",
        verbose_name="Собственник",
        blank=True,
        null=True,
    )

    activity_log = models.TextField(
        "Лог действий",
        blank=True,
        help_text="Произвольный текстовый лог изменений по задаче.",
    )

    created_at = models.DateTimeField("Создана", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлена", auto_now=True)
    closed_at = models.DateTimeField(
        "Закрыта",
        blank=True,
        null=True,
        help_text="Время перевода задачи в статус 'Выполнена'. Используется для SLA.",
    )

    class Meta:
        abstract = True
        ordering = ["-created_at"]


class CleaningTask(TaskBaseModel):
    """
    Задача на уборку.
    """

    is_pre_arrival = models.BooleanField("Предзаездная уборка", default=False)
    is_post_departure = models.BooleanField("Послезаселения уборка", default=False)
    is_general = models.BooleanField("Генеральная уборка", default=False)
    requires_quality_inspection = models.BooleanField(
        "Требует инспекции качества", default=False
    )

    def save(self, *args, **kwargs):
        self.task_type = self.TaskType.CLEANING
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Задача уборки"
        verbose_name_plural = "Задачи уборки"


class MaintenanceTask(TaskBaseModel):
    """
    Задача по эксплуатации / ремонту.
    """

    issue_type = models.CharField("Тип проблемы", max_length=255, blank=True)
    urgency = models.CharField("Срочность", max_length=100, blank=True)
    can_check_in = models.BooleanField("Можно заселять жильцов", default=True)

    executor_comment = models.TextField(
        "Комментарий исполнителя",
        blank=True,
        help_text="Обязателен при закрытии задачи.",
    )

    ai_problem_type = models.CharField(
        "AI: тип проблемы",
        max_length=100,
        blank=True,
        help_text="Например: plumbing, electricity, appliance.",
    )
    ai_urgency = models.CharField(
        "AI: срочность",
        max_length=20,
        blank=True,
        help_text="low | medium | high | critical.",
    )
    ai_recommendation = models.TextField(
        "AI: рекомендация",
        blank=True,
        help_text="Краткое пояснение/что сделать.",
    )
    ai_last_analyzed_at = models.DateTimeField(
        "AI: время последнего анализа",
        blank=True,
        null=True,
    )

    def save(self, *args, **kwargs):
        # Фиксация времени закрытия для SLA.
        if self.pk:
            old = MaintenanceTask.objects.get(pk=self.pk)
            status_changed_to_done = (
                old.status != self.Status.DONE and self.status == self.Status.DONE
            )
        else:
            status_changed_to_done = self.status == self.Status.DONE and self.closed_at is None

        if status_changed_to_done and self.closed_at is None:
            self.closed_at = timezone.now()

        self.task_type = self.TaskType.MAINTENANCE
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Задача по эксплуатации"
        verbose_name_plural = "Задачи по эксплуатации"


class CheckinTask(TaskBaseModel):
    """
    Задача на заселение гостя.
    """

    check_time = models.DateTimeField("Время заселения", blank=True, null=True)
    responsible_person = models.CharField(
        "Ответственный (ФИО/служба)", max_length=255, blank=True
    )
    checklist = models.TextField("Чек-лист", blank=True)

    def save(self, *args, **kwargs):
        self.task_type = self.TaskType.CHECKIN
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Задача заселения"
        verbose_name_plural = "Задачи заселения"


class CheckoutTask(TaskBaseModel):
    """
    Задача на выселение гостя.
    """

    checkout_time = models.DateTimeField("Время выселения", blank=True, null=True)
    responsible_person = models.CharField(
        "Ответственный (ФИО/служба)", max_length=255, blank=True
    )
    checklist = models.TextField("Чек-лист", blank=True)

    def save(self, *args, **kwargs):
        self.task_type = self.TaskType.CHECKOUT
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Задача выселения"
        verbose_name_plural = "Задачи выселения"


class QualityInspectionTask(TaskBaseModel):
    """
    Контроль качества уборки / состояния юнита.
    """

    cleaning_task = models.ForeignKey(
        "CleaningTask",
        on_delete=models.SET_NULL,
        related_name="quality_inspections",
        verbose_name="Связанная задача уборки",
        blank=True,
        null=True,
    )
    scores = models.JSONField(
        "Оценки по чек-листу",
        default=dict,
        blank=True,
        help_text="Структура чек-листа и оценок (JSON).",
    )

    def save(self, *args, **kwargs):
        self.task_type = self.TaskType.QUALITY
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Задача контроля качества"
        verbose_name_plural = "Задачи контроля качества"


class OwnerRequestTask(TaskBaseModel):
    """
    Запрос от собственника.
    """

    request_details = models.TextField("Детали запроса", blank=True)

    def save(self, *args, **kwargs):
        self.task_type = self.TaskType.OWNER_REQUEST
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Задача по запросу собственника"
        verbose_name_plural = "Задачи по запросам собственников"


class TaskPhoto(models.Model):
    """
    Фото, прикреплённое к задаче (любой из типов) через GenericForeignKey.
    """

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    task = GenericForeignKey("content_type", "object_id")

    image = models.FileField("Фото", upload_to="task_photos/")
    is_after = models.BooleanField(
        "Фото после выполнения работ",
        default=False,
        help_text="Отметьте, если фото сделано после выполнения задачи (для SLA/качества).",
    )
    uploaded_at = models.DateTimeField("Загружено", auto_now_add=True)

    class Meta:
        verbose_name = "Фото задачи"
        verbose_name_plural = "Фото задач"
