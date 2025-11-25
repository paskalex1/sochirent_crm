import calendar
from collections import defaultdict
from datetime import date
from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.bookings.models import Booking, CalendarEvent
from apps.finance.models import FinanceRecord
from apps.operations.models import (
    CleaningTask,
    MaintenanceTask,
    QualityInspectionTask,
    TaskBaseModel,
)
from apps.staff.models import Staff
from apps.staff.permissions import IsPropertyManagerDashboardRole
from .models import Property, RoomType, Unit, UnitPhoto


def calculate_hotel_stats(prop: Property, year: int, month: int) -> dict:
    """
    Считает помесячные метрики по отелю:
    - summary (occupancy_avg, adr_avg, revpar_avg, rooms_revenue_total);
    - разрез по дням (occupancy, adr, revpar).
    """
    period_start = date(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    period_end = date(year, month, last_day)

    # Всего активных номеров в отеле.
    rooms_total = prop.units.filter(
        status=Unit.Status.ACTIVE,
        is_active=True,
    ).count()

    # Подготовка структур для накопления данных по дням.
    day_units: dict[date, set[int]] = defaultdict(set)
    day_revenue: dict[date, Decimal] = defaultdict(lambda: Decimal("0.00"))

    # Все бронирования, пересекающиеся с периодом.
    bookings_qs = Booking.objects.filter(
        property=prop,
        check_in__lt=period_end,
        check_out__gt=period_start,
    ).select_related("unit")

    for booking in bookings_qs:
        total_nights = (booking.check_out - booking.check_in).days
        if total_nights <= 0:
            continue

        revenue_per_night = (booking.amount or Decimal("0.00")) / total_nights

        # Диапазон ночей в рамках интересующего нас периода.
        start = max(booking.check_in, period_start)
        end = min(booking.check_out, period_end + timezone.timedelta(days=1))

        current = start
        while current < end and current <= period_end:
            day_units[current].add(booking.unit_id)
            day_revenue[current] += revenue_per_night
            current += timezone.timedelta(days=1)

    # Формируем список дней с метриками.
    days_data = []
    current = period_start
    occupancy_values = []
    total_rooms_revenue = Decimal("0.00")
    total_rooms_occupied = 0
    days_in_period = (period_end - period_start).days + 1

    while current <= period_end:
        occupied = len(day_units.get(current, set()))
        revenue = day_revenue.get(current, Decimal("0.00"))

        if rooms_total > 0:
            occupancy = occupied / rooms_total
        else:
            occupancy = None

        if occupied > 0:
            adr = revenue / occupied
        else:
            adr = None

        if rooms_total > 0:
            revpar = revenue / rooms_total
        else:
            revpar = None

        days_data.append(
            {
                "date": current.isoformat(),
                "rooms_total": rooms_total,
                "rooms_occupied": occupied,
                "occupancy": float(occupancy) if occupancy is not None else None,
                "rooms_revenue": float(revenue),
                "adr": float(adr) if adr is not None else None,
                "revpar": float(revpar) if revpar is not None else None,
            }
        )

        if occupancy is not None:
            occupancy_values.append(occupancy)
        total_rooms_revenue += revenue
        total_rooms_occupied += occupied

        current += timezone.timedelta(days=1)

    # Агрегаты по периоду.
    if occupancy_values:
        occupancy_avg = sum(occupancy_values) / len(occupancy_values)
    else:
        occupancy_avg = None

    if total_rooms_occupied > 0:
        adr_avg = total_rooms_revenue / total_rooms_occupied
    else:
        adr_avg = None

    if rooms_total > 0 and days_in_period > 0:
        revpar_avg = total_rooms_revenue / (rooms_total * days_in_period)
    else:
        revpar_avg = None

    summary = {
        "rooms_total": rooms_total,
        "rooms_revenue_total": float(total_rooms_revenue),
        "occupancy_avg": float(occupancy_avg) if occupancy_avg is not None else None,
        "adr_avg": float(adr_avg) if adr_avg is not None else None,
        "revpar_avg": float(revpar_avg) if revpar_avg is not None else None,
    }

    return {
        "property_id": prop.id,
        "period": {"year": year, "month": month},
        "summary": summary,
        "days": days_data,
    }


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
        data = calculate_hotel_stats(prop, year, month)
        return Response(data)

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


class GMDashboardView(APIView):
    """
    Панель управляющего отелем (GM).

    Возвращает агрегированные данные только по объектам (Property)
    типа hotel, закреплённым за текущим пользователем с ролью GM.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
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

        user = request.user
        try:
            staff: Staff = user.staff_profile  # type: ignore[attr-defined]
        except Staff.DoesNotExist:
            return Response(
                {"detail": "Для пользователя не найден профиль Staff."},
                status=400,
            )

        if staff.role != Staff.Role.GM:
            return Response(
                {"detail": "Доступ к панели GM разрешён только пользователям с ролью GM."},
                status=403,
            )

        properties_qs = (
            Property.objects.select_related("owner", "manager")
            .filter(
                id__in=staff.properties.values_list("id", flat=True),
                type=Property.PropertyType.HOTEL,
            )
            .order_by("name")
        )

        if not properties_qs.exists():
            return Response(
                {
                    "detail": (
                        "За данным GM не закреплены объекты типа 'hotel'. "
                        "Панель недоступна."
                    )
                },
                status=400,
            )

        active_statuses = [
            TaskBaseModel.Status.NEW,
            TaskBaseModel.Status.IN_PROGRESS,
        ]

        dashboard_properties = []

        for prop in properties_qs:
            # Статистика загрузки и выручки по отелю за период.
            stats = calculate_hotel_stats(prop, year, month)

            # Юниты отеля.
            units_qs = prop.units.all()
            units_data = UnitSerializer(units_qs, many=True).data

            # Текущие и будущие бронирования по отелю.
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

            # Активные задачи по клинингу и эксплуатации по отелю.
            cleaning_qs = CleaningTask.objects.filter(
                property=prop,
                status__in=active_statuses,
            ).select_related("unit", "executor")
            maintenance_qs = MaintenanceTask.objects.filter(
                property=prop,
                status__in=active_statuses,
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
                        "deadline",
                    ]

            cleaning_data = TaskMiniSerializer(cleaning_qs, many=True).data
            maintenance_data = TaskMiniSerializer(maintenance_qs, many=True).data

            dashboard_properties.append(
                {
                    "property": PropertySerializer(prop).data,
                    "units": units_data,
                    "bookings": bookings_data,
                    "tasks": {
                        "cleaning": cleaning_data,
                        "maintenance": maintenance_data,
                    },
                    "stats": stats,
                }
            )

        return Response({"properties": dashboard_properties})


class PropertyManagerDashboardView(APIView):
    """
    Панель Property Manager (CRM).

    Доступна ролям: PropertyManager, COO, CEO.
    """

    permission_classes = [IsPropertyManagerDashboardRole]

    def get(self, request, *args, **kwargs):
        now = timezone.now()
        today = now.date()
        try:
            year = int(request.query_params.get("year", today.year))
        except (TypeError, ValueError):
            year = today.year
        try:
            month = int(request.query_params.get("month", today.month))
        except (TypeError, ValueError):
            month = today.month

        month = max(1, min(12, month))

        try:
            staff: Staff = request.user.staff_profile  # type: ignore[attr-defined]
        except Staff.DoesNotExist:
            return Response(
                {"detail": "Для пользователя не найден профиль Staff."},
                status=400,
            )

        # Определяем набор объектов для дашборда.
        if staff.role in (Staff.Role.CEO, Staff.Role.COO):
            properties_qs = Property.objects.all().order_by("name")
        else:
            properties_qs = (
                Property.objects.filter(id__in=staff.properties.values_list("id", flat=True))
                .order_by("name")
            )

        active_statuses = [
            TaskBaseModel.Status.NEW,
            TaskBaseModel.Status.IN_PROGRESS,
        ]

        properties_data = []

        total_active_tasks = 0
        total_overdue_tasks = 0

        # Агрегаты по загрузке.
        occupancy_values = []
        total_rooms_revenue = 0.0
        total_rooms = 0

        for prop in properties_qs:
            # Загрузка / метрики по периоду.
            if prop.type == Property.PropertyType.HOTEL:
                stats = calculate_hotel_stats(prop, year, month)
                stats_summary = stats["summary"]
                if stats_summary["rooms_total"]:
                    total_rooms += stats_summary["rooms_total"]
                total_rooms_revenue += stats_summary["rooms_revenue_total"]
                if stats_summary["occupancy_avg"] is not None:
                    occupancy_values.append(stats_summary["occupancy_avg"])
            else:
                stats_summary = None

            # Задачи по объекту.
            base_filter = {"property": prop, "status__in": active_statuses}
            cleaning_qs = CleaningTask.objects.filter(**base_filter)
            maintenance_qs = MaintenanceTask.objects.filter(**base_filter)
            checkin_qs = CheckinTask.objects.filter(**base_filter)
            checkout_qs = CheckoutTask.objects.filter(**base_filter)
            quality_qs = QualityInspectionTask.objects.filter(**base_filter)
            owner_req_qs = OwnerRequestTask.objects.filter(**base_filter)

            cleaning_active = cleaning_qs.count()
            maintenance_active = maintenance_qs.count()
            checkin_active = checkin_qs.count()
            checkout_active = checkout_qs.count()
            quality_active = quality_qs.count()
            owner_req_active = owner_req_qs.count()

            overdue_filter = {"deadline__lt": now}
            cleaning_overdue = cleaning_qs.filter(**overdue_filter).count()
            maintenance_overdue = maintenance_qs.filter(**overdue_filter).count()
            checkin_overdue = checkin_qs.filter(**overdue_filter).count()
            checkout_overdue = checkout_qs.filter(**overdue_filter).count()
            quality_overdue = quality_qs.filter(**overdue_filter).count()
            owner_req_overdue = owner_req_qs.filter(**overdue_filter).count()

            active_total = (
                cleaning_active
                + maintenance_active
                + checkin_active
                + checkout_active
                + quality_active
                + owner_req_active
            )
            overdue_total = (
                cleaning_overdue
                + maintenance_overdue
                + checkin_overdue
                + checkout_overdue
                + quality_overdue
                + owner_req_overdue
            )

            total_active_tasks += active_total
            total_overdue_tasks += overdue_total

            properties_data.append(
                {
                    "property": PropertySerializer(prop).data,
                    "period": {"year": year, "month": month},
                    "stats": stats_summary,
                    "tasks": {
                        "active_total": active_total,
                        "overdue_total": overdue_total,
                        "by_type": {
                            "cleaning": {
                                "active": cleaning_active,
                                "overdue": cleaning_overdue,
                            },
                            "maintenance": {
                                "active": maintenance_active,
                                "overdue": maintenance_overdue,
                            },
                            "checkin": {
                                "active": checkin_active,
                                "overdue": checkin_overdue,
                            },
                            "checkout": {
                                "active": checkout_active,
                                "overdue": checkout_overdue,
                            },
                            "quality": {
                                "active": quality_active,
                                "overdue": quality_overdue,
                            },
                            "owner_request": {
                                "active": owner_req_active,
                                "overdue": owner_req_overdue,
                            },
                        },
                    },
                }
            )

        if occupancy_values:
            occupancy_avg = sum(occupancy_values) / len(occupancy_values)
        else:
            occupancy_avg = None

        summary = {
            "properties_count": properties_qs.count(),
            "tasks_active_total": total_active_tasks,
            "tasks_overdue_total": total_overdue_tasks,
            "rooms_total": total_rooms,
            "rooms_revenue_total": total_rooms_revenue,
            "occupancy_avg": occupancy_avg,
        }

        return Response(
            {
                "period": {"year": year, "month": month},
                "properties": properties_data,
                "summary": summary,
            }
        )
