from django.db.models import Avg, DurationField, ExpressionWrapper, F
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import serializers, viewsets
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.properties.models import Property
from apps.staff.models import Staff
from .models import (
    CheckinTask,
    CheckoutTask,
    CleaningTask,
    MaintenanceTask,
    OwnerRequestTask,
    QualityInspectionTask,
)


class TaskBaseSerializer(serializers.ModelSerializer):
    class Meta:
        fields = [
            "id",
            "title",
            "description",
            "task_type",
            "status",
            "priority",
            "executor",
            "deadline",
            "property",
            "unit",
            "booking",
            "owner",
            "activity_log",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "task_type", "created_at", "updated_at"]


class CleaningTaskSerializer(TaskBaseSerializer):
    class Meta(TaskBaseSerializer.Meta):
        model = CleaningTask
        fields = TaskBaseSerializer.Meta.fields + [
            "is_pre_arrival",
            "is_post_departure",
            "is_general",
        ]


class MaintenanceTaskSerializer(TaskBaseSerializer):
    class Meta(TaskBaseSerializer.Meta):
        model = MaintenanceTask
        fields = TaskBaseSerializer.Meta.fields + [
            "issue_type",
            "urgency",
            "can_check_in",
            "ai_problem_type",
            "ai_urgency",
            "ai_recommendation",
            "ai_last_analyzed_at",
        ]
        read_only_fields = TaskBaseSerializer.Meta.read_only_fields + [
            "ai_problem_type",
            "ai_urgency",
            "ai_recommendation",
            "ai_last_analyzed_at",
        ]


class CheckinTaskSerializer(TaskBaseSerializer):
    class Meta(TaskBaseSerializer.Meta):
        model = CheckinTask
        fields = TaskBaseSerializer.Meta.fields + [
            "check_time",
            "responsible_person",
            "checklist",
        ]


class CheckoutTaskSerializer(TaskBaseSerializer):
    class Meta(TaskBaseSerializer.Meta):
        model = CheckoutTask
        fields = TaskBaseSerializer.Meta.fields + [
            "checkout_time",
            "responsible_person",
            "checklist",
        ]


class QualityInspectionTaskSerializer(TaskBaseSerializer):
    class Meta(TaskBaseSerializer.Meta):
        model = QualityInspectionTask
        fields = TaskBaseSerializer.Meta.fields + [
            "cleaning_task",
            "scores",
        ]


class OwnerRequestTaskSerializer(TaskBaseSerializer):
    class Meta(TaskBaseSerializer.Meta):
        model = OwnerRequestTask
        fields = TaskBaseSerializer.Meta.fields + [
            "request_details",
        ]


class BaseTaskViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = [
        "task_type",
        "status",
        "priority",
        "executor",
        "property",
        "unit",
        "booking",
        "owner",
        "deadline",
    ]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user.is_authenticated:
            return qs

        try:
            staff: Staff = user.staff_profile  # type: ignore[attr-defined]
        except Staff.DoesNotExist:
            return qs

        # GM: только задачи по закрепленным объектам.
        if staff.role == Staff.Role.GM:
            return qs.filter(property__in=staff.properties.all())

        # HotelDirector: только задачи по объектам-отелям.
        if staff.role == Staff.Role.HOTEL_DIRECTOR:
            return qs.filter(property__type=Property.PropertyType.HOTEL)

        return qs


class CleaningTaskViewSet(BaseTaskViewSet):
    queryset = CleaningTask.objects.all()
    serializer_class = CleaningTaskSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user.is_authenticated:
            return qs

        try:
            staff: Staff = user.staff_profile  # type: ignore[attr-defined]
        except Staff.DoesNotExist:
            staff = None  # type: ignore[assignment]

        # Сотрудники Cleaning видят только задачи, где они указаны исполнителями.
        if staff is not None and staff.role == Staff.Role.CLEANING:
            return qs.filter(executor=user)

        return qs


class MaintenanceTaskViewSet(BaseTaskViewSet):
    queryset = MaintenanceTask.objects.all()
    serializer_class = MaintenanceTaskSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user.is_authenticated:
            return qs

        try:
            staff: Staff = user.staff_profile  # type: ignore[attr-defined]
        except Staff.DoesNotExist:
            staff = None  # type: ignore[assignment]

        if staff is not None and staff.role == Staff.Role.MAINTENANCE:
            return qs

        return qs


class CheckinTaskViewSet(BaseTaskViewSet):
    queryset = CheckinTask.objects.all()
    serializer_class = CheckinTaskSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user.is_authenticated:
            return qs

        try:
            staff: Staff = user.staff_profile  # type: ignore[attr-defined]
        except Staff.DoesNotExist:
            staff = None  # type: ignore[assignment]

        # FrontDesk: только задачи check-in по своим объектам.
        if staff is not None and staff.role == Staff.Role.FRONT_DESK:
            return qs.filter(property__in=staff.properties.all())

        return qs


class CheckoutTaskViewSet(BaseTaskViewSet):
    queryset = CheckoutTask.objects.all()
    serializer_class = CheckoutTaskSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user.is_authenticated:
            return qs

        try:
            staff: Staff = user.staff_profile  # type: ignore[attr-defined]
        except Staff.DoesNotExist:
            staff = None  # type: ignore[assignment]

        # FrontDesk: только задачи check-out по своим объектам.
        if staff is not None and staff.role == Staff.Role.FRONT_DESK:
            return qs.filter(property__in=staff.properties.all())

        return qs


class QualityInspectionTaskViewSet(BaseTaskViewSet):
    queryset = QualityInspectionTask.objects.all()
    serializer_class = QualityInspectionTaskSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user.is_authenticated:
            return qs

        try:
            staff: Staff = user.staff_profile  # type: ignore[attr-defined]
        except Staff.DoesNotExist:
            staff = None  # type: ignore[assignment]

        if staff is not None and staff.role == Staff.Role.QUALITY:
            return qs

        return qs


class OwnerRequestTaskViewSet(BaseTaskViewSet):
    queryset = OwnerRequestTask.objects.all()
    serializer_class = OwnerRequestTaskSerializer


class MaintenanceSLAReportView(APIView):
    """
    Простой отчёт по SLA для задач эксплуатации (MaintenanceTask).

    Возвращает среднее время решения (в часах) и количество закрытых задач.
    """

    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request, *args, **kwargs):
        qs = MaintenanceTask.objects.filter(
            closed_at__isnull=False,
        )

        # Фильтр по объекту, если передан.
        property_id = request.query_params.get("property")
        if property_id:
            qs = qs.filter(property_id=property_id)

        resolution_expr = ExpressionWrapper(
            F("closed_at") - F("created_at"),
            output_field=DurationField(),
        )
        qs = qs.annotate(resolution_time=resolution_expr)

        data = qs.aggregate(
            avg_resolution=Avg("resolution_time"),
            count=models.Count("id"),
        )

        avg_resolution = data["avg_resolution"]
        avg_hours = None
        if avg_resolution is not None:
            avg_hours = round(avg_resolution.total_seconds() / 3600, 2)

        return Response(
            {
                "count_closed_tasks": data["count"] or 0,
                "average_resolution_hours": avg_hours,
            }
        )
