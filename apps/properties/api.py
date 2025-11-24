import calendar
from datetime import date

from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from apps.bookings.models import Booking, CalendarEvent
from apps.finance.models import FinanceRecord
from apps.operations.models import (
    CleaningTask,
    MaintenanceTask,
    QualityInspectionTask,
    TaskBaseModel,
)
from apps.staff.models import Staff
from .models import Property, RoomType, Unit, UnitPhoto


class PropertySerializer(serializers.ModelSerializer):
    class Meta:
        model = Property
        fields = [
            "id",
            "owner",
            "type",
            "name",
            "city",
            "district",
            "address",
            "status",
            "manager",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class UnitSerializer(serializers.ModelSerializer):
    photos = serializers.SerializerMethodField()
    room_type = serializers.PrimaryKeyRelatedField(
        queryset=RoomType.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = Unit
        fields = [
            "id",
            "property",
            "type",
            "code",
            "room_type",
            "description",
            "floor",
            "area",
            "capacity",
            "status",
            "is_active",
            "created_at",
            "updated_at",
            "photos",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_photos(self, obj):
        photos = obj.photos.all()

        class PhotoMiniSerializer(serializers.ModelSerializer):
            class Meta:
                model = UnitPhoto
                fields = ["id", "image", "caption", "created_at"]

        return PhotoMiniSerializer(photos, many=True).data


class PropertyViewSet(viewsets.ModelViewSet):
    queryset = Property.objects.select_related("owner", "manager").all()
    serializer_class = PropertySerializer
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

        # GM видит только закрепленные за ним объекты.
        if staff.role == Staff.Role.GM:
            return qs.filter(id__in=staff.properties.values_list("id", flat=True))

        # HotelDirector видит только объекты с типом hotel.
        if staff.role == Staff.Role.HOTEL_DIRECTOR:
            return qs.filter(type=Property.PropertyType.HOTEL)

        return qs

    @action(detail=True, methods=["get"], url_path="hotel-occupancy")
    def hotel_occupancy(self, request, pk=None):
        """
        Агрегированная загрузка по отелю (Property с типом hotel) по дням месяца.

        Параметры:
          - year (int)
          - month (int, 1–12)
        По умолчанию — текущий месяц.
        Ответ:
        {
          "period": {"year": ..., "month": ...},
          "days": [
            {"date": "YYYY-MM-DD", "rooms_total": N, "rooms_occupied": M},
            ...
          ]
        }
        """
        prop = self.get_object()
        if prop.type != Property.PropertyType.HOTEL:
            return Response(
                {"detail": "Загрузка по отелю доступна только для объектов типа 'hotel'."},
                status=400,
            )

        now = timezone.now().date()
        try:
            year = int(request.query_params.get("year", now.year))
        except (TypeError, ValueError):
            year = now.year
        try:
            month = int(request.query_params.get("month", now.month))
        except (TypeError, ValueError):
            month = now.month

        month = max(1, min(12, month))
        period_start = date(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        period_end = date(year, month, last_day)

        # Общее количество номеров: rooms_count или количество юнитов.
        rooms_total = prop.rooms_count or prop.units.count()

        days_data = []
        current = period_start

        # Предзагружаем бронирования по объекту за период.
        bookings_qs = Booking.objects.filter(
            property=prop,
            check_in__lt=period_end,
            check_out__gt=period_start,
        ).select_related("unit")

        while current <= period_end:
            # Считаем количество занятых юнитов в конкретный день.
            occupied_units = bookings_qs.filter(
                check_in__lte=current,
                check_out__gt=current,
            ).values_list("unit_id", flat=True).distinct().count()

            days_data.append(
                {
                    "date": current.isoformat(),
                    "rooms_total": rooms_total,
                    "rooms_occupied": occupied_units,
                }
            )
            current = current + timezone.timedelta(days=1)

        return Response(
            {
                "period": {"year": year, "month": month},
                "days": days_data,
            }
        )

    @action(detail=True, methods=["get"], url_path="card")
    def card(self, request, pk=None):
        """
        Карточка объекта Property с агрегированными данными.

        Поддерживает query-параметры:
          - year (int)
          - month (int, 1–12)
        Если не заданы — используется текущий месяц.
        """
        prop = self.get_object()

        # Период.
        now = timezone.now().date()
        try:
            year = int(request.query_params.get("year", now.year))
        except (TypeError, ValueError):
            year = now.year
        try:
            month = int(request.query_params.get("month", now.month))
        except (TypeError, ValueError):
            month = now.month

        month = max(1, min(12, month))
        period_start = date(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        period_end = date(year, month, last_day)

        # Юниты.
        units_qs = prop.units.all()
        units_data = UnitSerializer(units_qs, many=True).data

        # Текущие и будущие бронирования по объекту.
        today = now
        bookings_qs = (
            Booking.objects.filter(property=prop, check_out__gte=today)
            .select_related("unit", "guest")
            .order_by("check_in")
        )

        class BookingMiniSerializer(serializers.ModelSerializer):
            class Meta:
                model = Booking
                fields = [
                    "id",
                    "unit",
                    "guest",
                    "check_in",
                    "check_out",
                    "status",
                    "source",
                    "amount",
                    "currency",
                ]

        bookings_data = BookingMiniSerializer(bookings_qs, many=True).data

        # Активные задачи по объекту.
        active_statuses = [
            TaskBaseModel.Status.NEW,
            TaskBaseModel.Status.IN_PROGRESS,
        ]

        cleaning_qs = CleaningTask.objects.filter(
            property=prop, status__in=active_statuses
        ).select_related("unit", "executor")
        maintenance_qs = MaintenanceTask.objects.filter(
            property=prop, status__in=active_statuses
        ).select_related("unit", "executor")
        quality_qs = QualityInspectionTask.objects.filter(
            property=prop, status__in=active_statuses
        ).select_related("unit", "executor")

        class TaskMiniSerializer(serializers.ModelSerializer):
            class Meta:
                model = TaskBaseModel
                fields = [
                    "id",
                    "task_type",
                    "title",
                    "status",
                    "priority",
                    "executor",
                    "unit",
                    "booking",
                    "deadline",
                ]

        cleaning_data = TaskMiniSerializer(cleaning_qs, many=True).data
        maintenance_data = TaskMiniSerializer(maintenance_qs, many=True).data
        quality_data = TaskMiniSerializer(quality_qs, many=True).data

        # Статистика загрузки (occupancy) за период.
        period_bookings = Booking.objects.filter(
            property=prop,
            check_in__lte=period_end,
            check_out__gte=period_start,
        )

        total_nights = (period_end - period_start).days + 1
        booked_nights = 0

        for b in period_bookings:
            start = max(b.check_in, period_start)
            end = min(b.check_out, period_end)
            delta = (end - start).days
            if delta > 0:
                booked_nights += delta

        occupancy_percent = (
            round(booked_nights / total_nights * 100, 2) if total_nights > 0 else 0.0
        )

        # Финансовая статистика по FinanceRecord за период.
        fin_qs = FinanceRecord.objects.filter(
            property=prop,
            operation_date__gte=period_start,
            operation_date__lte=period_end,
        )

        finance_summary = []
        for row in (
            fin_qs.values("currency")
            .annotate(
                income_total=models.Sum(
                    "amount",
                    filter=models.Q(
                        record_type=FinanceRecord.RecordType.INCOME,
                    ),
                ),
                expense_total=models.Sum(
                    "amount",
                    filter=models.Q(
                        record_type=FinanceRecord.RecordType.EXPENSE,
                    ),
                ),
            )
            .order_by("currency")
        ):
            income = row["income_total"] or 0
            expense = row["expense_total"] or 0
            net = income - expense
            finance_summary.append(
                {
                    "currency": row["currency"],
                    "income_total": income,
                    "expense_total": expense,
                    "net_total": net,
                }
            )

        # Вкладка "Собственник".
        owner = prop.owner
        owner_data = {
            "id": owner.id,
            "name": owner.name,
            "phone": owner.phone,
            "email": owner.email,
            "status": owner.status,
        }

        return Response(
            {
                "property": PropertySerializer(prop).data,
                "period": {"year": year, "month": month},
                "units": units_data,
                "bookings": bookings_data,
                "tasks": {
                    "cleaning": cleaning_data,
                    "maintenance": maintenance_data,
                    "quality_inspection": quality_data,
                },
                "stats": {
                    "total_nights": total_nights,
                    "booked_nights": booked_nights,
                    "occupancy_percent": occupancy_percent,
                },
                "finance_summary": finance_summary,
                "owner": owner_data,
            }
        )


class UnitViewSet(viewsets.ModelViewSet):
    queryset = Unit.objects.select_related("property", "property__owner").all()
    serializer_class = UnitSerializer
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

        if staff.role == Staff.Role.GM:
            return qs.filter(property__in=staff.properties.all())

        if staff.role == Staff.Role.HOTEL_DIRECTOR:
            return qs.filter(property__type=Property.PropertyType.HOTEL)

        return qs

    @action(detail=True, methods=["get"], url_path="card")
    def card(self, request, pk=None):
        """
        Карточка юнита Unit.

        Содержит:
          - параметры юнита;
          - календарь занятости (CalendarEvent + Booking) за период;
          - историю бронирований;
          - активные и последние задачи по клинингу и ремонту;
          - описание и фото.

        Период задаётся query-параметрами:
          - year (int)
          - month (int, 1–12)
        По умолчанию — текущий месяц.
        """
        unit = self.get_object()

        now = timezone.now().date()
        try:
            year = int(request.query_params.get("year", now.year))
        except (TypeError, ValueError):
            year = now.year
        try:
            month = int(request.query_params.get("month", now.month))
        except (TypeError, ValueError):
            month = now.month

        month = max(1, min(12, month))
        period_start = date(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        period_end = date(year, month, last_day)

        # Базовые данные по юниту.
        unit_data = UnitSerializer(unit).data

        # Календарь занятости: события CalendarEvent за период.
        cal_events = CalendarEvent.objects.filter(
            unit=unit,
            start_date__lte=period_end,
            end_date__gte=period_start,
        ).select_related("booking")

        event_type_filter = request.query_params.get("event_type")
        if event_type_filter:
            types = [t.strip() for t in event_type_filter.split(",") if t.strip()]
            if types:
                cal_events = cal_events.filter(event_type__in=types)

        class CalendarEventSerializer(serializers.ModelSerializer):
            class Meta:
                model = CalendarEvent
                fields = [
                    "id",
                    "event_type",
                    "start_date",
                    "end_date",
                    "booking",
                    "note",
                ]

        calendar_data = CalendarEventSerializer(cal_events, many=True).data

        # История бронирований по юниту (можно ограничить последними N).
        bookings_qs = (
            Booking.objects.filter(unit=unit)
            .select_related("guest", "property")
            .order_by("-check_in", "-id")[:100]
        )

        class BookingMiniSerializer(serializers.ModelSerializer):
            class Meta:
                model = Booking
                fields = [
                    "id",
                    "property",
                    "guest",
                    "check_in",
                    "check_out",
                    "status",
                    "source",
                    "amount",
                    "currency",
                ]

        bookings_data = BookingMiniSerializer(bookings_qs, many=True).data

        # Активные и последние задачи по клинингу и ремонту.
        active_statuses = [
            TaskBaseModel.Status.NEW,
            TaskBaseModel.Status.IN_PROGRESS,
        ]

        cleaning_active = CleaningTask.objects.filter(
            unit=unit, status__in=active_statuses
        ).select_related("executor")
        maintenance_active = MaintenanceTask.objects.filter(
            unit=unit, status__in=active_statuses
        ).select_related("executor")

        cleaning_recent = (
            CleaningTask.objects.filter(unit=unit)
            .exclude(id__in=cleaning_active.values_list("id", flat=True))
            .order_by("-created_at")[:20]
        )
        maintenance_recent = (
            MaintenanceTask.objects.filter(unit=unit)
            .exclude(id__in=maintenance_active.values_list("id", flat=True))
            .order_by("-created_at")[:20]
        )

        class TaskMiniSerializer(serializers.ModelSerializer):
            class Meta:
                model = TaskBaseModel
                fields = [
                    "id",
                    "task_type",
                    "title",
                    "status",
                    "priority",
                    "executor",
                    "deadline",
                ]

        cleaning_active_data = TaskMiniSerializer(cleaning_active, many=True).data
        maintenance_active_data = TaskMiniSerializer(maintenance_active, many=True).data
        cleaning_recent_data = TaskMiniSerializer(cleaning_recent, many=True).data
        maintenance_recent_data = TaskMiniSerializer(maintenance_recent, many=True).data

        return Response(
            {
                "unit": unit_data,
                "period": {"year": year, "month": month},
                "calendar": calendar_data,
                "bookings": bookings_data,
                "tasks": {
                    "cleaning_active": cleaning_active_data,
                    "maintenance_active": maintenance_active_data,
                    "cleaning_recent": cleaning_recent_data,
                    "maintenance_recent": maintenance_recent_data,
                },
            }
        )
