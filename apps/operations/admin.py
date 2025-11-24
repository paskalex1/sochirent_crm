from django.contrib import admin

from .models import (
    CheckinTask,
    CheckoutTask,
    CleaningTask,
    MaintenanceTask,
    OwnerRequestTask,
    QualityInspectionTask,
    TaskPhoto,
)


class BaseTaskAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "task_type",
        "status",
        "priority",
        "executor",
        "property",
        "unit",
        "booking",
        "owner",
        "deadline",
        "created_at",
    )
    list_filter = ("task_type", "status", "priority", "executor", "property", "unit")
    search_fields = ("title", "description", "activity_log")


@admin.register(CleaningTask)
class CleaningTaskAdmin(BaseTaskAdmin):
    list_display = BaseTaskAdmin.list_display + (
        "is_pre_arrival",
        "is_post_departure",
        "is_general",
    )


@admin.register(MaintenanceTask)
class MaintenanceTaskAdmin(BaseTaskAdmin):
    list_display = BaseTaskAdmin.list_display + (
        "issue_type",
        "urgency",
        "can_check_in",
        "closed_at",
    )


@admin.register(CheckinTask)
class CheckinTaskAdmin(BaseTaskAdmin):
    list_display = BaseTaskAdmin.list_display + ("check_time", "responsible_person")


@admin.register(CheckoutTask)
class CheckoutTaskAdmin(BaseTaskAdmin):
    list_display = BaseTaskAdmin.list_display + ("checkout_time", "responsible_person")


@admin.register(QualityInspectionTask)
class QualityInspectionTaskAdmin(BaseTaskAdmin):
    list_display = BaseTaskAdmin.list_display + ("cleaning_task",)


@admin.register(OwnerRequestTask)
class OwnerRequestTaskAdmin(BaseTaskAdmin):
    list_display = BaseTaskAdmin.list_display + ("request_details",)


@admin.register(TaskPhoto)
class TaskPhotoAdmin(admin.ModelAdmin):
    list_display = ("id", "content_type", "object_id", "uploaded_at")
    list_filter = ("content_type",)
