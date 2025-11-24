from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from apps.operations.models import CheckinTask, CheckoutTask, CleaningTask
from apps.operations.services import sync_cleaning_tasks_for_booking
from apps.properties.models import Property
from apps.staff.models import Staff
from .models import Booking, BookingStatusLog, CalendarEvent, Guest, RatePlan


class GuestSerializer(serializers.ModelSerializer):
    class Meta:
        model = Guest
        fields = [
            "id",
            "full_name",
            "phone",
            "email",
            "document_type",
            "document_number",
            "country",
            "city",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class RatePlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = RatePlan
        fields = [
            "id",
            "property",
            "name",
            "description",
            "base_price",
            "params",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class BookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        fields = [
            "id",
            "unit",
            "property",
            "guest",
            "rate_plan",
            "owner",
            "check_in",
            "check_out",
            "status",
            "source",
            "amount",
            "currency",
            "prepayment_amount",
            "payment_status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class BookingStatusLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookingStatusLog
        fields = [
            "id",
            "old_status",
            "new_status",
            "changed_at",
            "changed_by",
        ]
        read_only_fields = fields


class CalendarEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = CalendarEvent
        fields = [
            "id",
            "unit",
            "booking",
            "event_type",
            "start_date",
            "end_date",
            "note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class GuestViewSet(viewsets.ModelViewSet):
    queryset = Guest.objects.all().order_by("full_name")
    serializer_class = GuestSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user.is_authenticated:
            return qs

        try:
            staff: Staff = user.staff_profile  # type: ignore[attr-defined]
        except Staff.DoesNotExist:
            return qs

        # FrontDesk и GM видят только гостей по своим объектам.
        if staff.role in {Staff.Role.GM, Staff.Role.FRONT_DESK}:
            props = staff.properties.all()
            return qs.filter(bookings__property__in=props).distinct()

        # HotelDirector — гости по объектам типа hotel.
        if staff.role == Staff.Role.HOTEL_DIRECTOR:
            return qs.filter(
                bookings__property__type=Property.PropertyType.HOTEL
            ).distinct()

        return qs


class RatePlanViewSet(viewsets.ModelViewSet):
    queryset = RatePlan.objects.select_related("property").all()
    serializer_class = RatePlanSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]


class BookingViewSet(viewsets.ModelViewSet):
    queryset = (
        Booking.objects.select_related("unit", "property", "guest", "rate_plan")
        .all()
        .order_by("-check_in", "-id")
    )
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = [
        "status",
        "source",
        "property",
        "unit",
        "check_in",
        "check_out",
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

        # GM: только бронирования по своим объектам.
        if staff.role == Staff.Role.GM:
            return qs.filter(property__in=staff.properties.all())

        # HotelDirector: только бронирования по объектам-отелям.
        if staff.role == Staff.Role.HOTEL_DIRECTOR:
            return qs.filter(property__type=Property.PropertyType.HOTEL)

        # FrontDesk: только бронирования по своим объектам.
        if staff.role == Staff.Role.FRONT_DESK:
            return qs.filter(property__in=staff.properties.all())

        return qs

    def _create_default_tasks_for_booking(self, booking: Booking) -> None:
        """
        Создаёт связанные задачи checkin/checkout и триггерит сервис клининга
        для краткосрочных / отельных объектов.
        """
        if booking.property.type not in [
            Property.PropertyType.RESIDENTIAL_SHORT,
            Property.PropertyType.HOTEL,
        ]:
            return

        # Задачи check-in и check-out создаём всегда для релевантных объектов.
        CheckinTask.objects.create(
            title=f"Заселение гостя {booking.guest.full_name}",
            description="Автоматически созданная задача заселения.",
            property=booking.property,
            unit=booking.unit,
            booking=booking,
        )
        CheckoutTask.objects.create(
            title=f"Выселение гостя {booking.guest.full_name}",
            description="Автоматически созданная задача выселения.",
            property=booking.property,
            unit=booking.unit,
            booking=booking,
        )

        # Клининг отдаем на сервис автоматизации.
        sync_cleaning_tasks_for_booking(booking)

    def perform_create(self, serializer):
        booking: Booking = serializer.save()
        self._create_default_tasks_for_booking(booking)

    def _log_status_change(self, booking: Booking, old_status: str, new_status: str):
        if old_status == new_status:
            return
        user = self.request.user if self.request.user.is_authenticated else None
        BookingStatusLog.objects.create(
            booking=booking,
            old_status=old_status,
            new_status=new_status,
            changed_by=user,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        old_status = instance.status
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        booking = serializer.instance
        new_status = booking.status
        self._log_status_change(booking, old_status, new_status)
        # Сервис клининга может создать/обновить задачи при изменении статуса/дат.
        sync_cleaning_tasks_for_booking(booking)
        return Response(serializer.data)

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    @action(detail=True, methods=["get"], url_path="card")
    def card(self, request, pk=None):
        """
        Карточка бронирования.

        Содержит:
          - данные брони;
          - данные гостя;
          - связанные задачи (CheckinTask, CheckoutTask, CleaningTask);
          - финансовые записи по брони (FinanceRecord);
          - историю изменений статусов (BookingStatusLog).
        """
        booking = self.get_object()

        # Бронь и гость.
        booking_data = BookingSerializer(booking).data
        guest_data = GuestSerializer(booking.guest).data

        # Задачи.
        checkin_tasks = CheckinTask.objects.filter(booking=booking)
        checkout_tasks = CheckoutTask.objects.filter(booking=booking)
        cleaning_tasks = CleaningTask.objects.filter(booking=booking)

        class TaskMiniSerializer(serializers.ModelSerializer):
            class Meta:
                model = CleaningTask
                fields = [
                    "id",
                    "task_type",
                    "title",
                    "status",
                    "priority",
                    "executor",
                    "deadline",
                ]

        checkin_data = TaskMiniSerializer(checkin_tasks, many=True).data
        checkout_data = TaskMiniSerializer(checkout_tasks, many=True).data
        cleaning_data = TaskMiniSerializer(cleaning_tasks, many=True).data

        # Финансовые записи по брони.
        from apps.finance.models import FinanceRecord  # локальный импорт, чтобы избежать циклов

        fin_qs = FinanceRecord.objects.filter(booking=booking)

        class FinanceMiniSerializer(serializers.ModelSerializer):
            class Meta:
                model = FinanceRecord
                fields = [
                    "id",
                    "record_type",
                    "category",
                    "amount",
                    "currency",
                    "operation_date",
                ]

        finance_data = FinanceMiniSerializer(fin_qs, many=True).data

        # История статусов.
        status_logs = booking.status_logs.all().order_by("changed_at")
        status_history = BookingStatusLogSerializer(status_logs, many=True).data

        return Response(
            {
                "booking": booking_data,
                "guest": guest_data,
                "tasks": {
                    "checkin": checkin_data,
                    "checkout": checkout_data,
                    "cleaning": cleaning_data,
                },
                "finance_records": finance_data,
                "status_history": status_history,
            }
        )


class CalendarEventViewSet(viewsets.ModelViewSet):
    queryset = CalendarEvent.objects.select_related("unit", "booking").all()
    serializer_class = CalendarEventSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
