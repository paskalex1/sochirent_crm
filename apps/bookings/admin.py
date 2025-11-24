from django.contrib import admin

from .models import Booking, BookingStatusLog, CalendarEvent, Guest, RatePlan


@admin.register(Guest)
class GuestAdmin(admin.ModelAdmin):
    list_display = ("full_name", "phone", "email", "country", "city", "created_at")
    search_fields = ("full_name", "phone", "email", "document_number")


@admin.register(RatePlan)
class RatePlanAdmin(admin.ModelAdmin):
    list_display = ("name", "property", "base_price", "is_active", "created_at")
    list_filter = ("property", "is_active")
    search_fields = ("name", "property__name")


class BookingStatusLogInline(admin.TabularInline):
    model = BookingStatusLog
    extra = 0
    readonly_fields = ("old_status", "new_status", "changed_at", "changed_by")


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "unit",
        "property",
        "guest",
        "check_in",
        "check_out",
        "status",
        "source",
        "amount",
        "currency",
    )
    list_filter = ("status", "source", "property", "unit")
    search_fields = ("id", "guest__full_name")
    date_hierarchy = "check_in"
    inlines = [BookingStatusLogInline]


@admin.register(CalendarEvent)
class CalendarEventAdmin(admin.ModelAdmin):
    list_display = ("unit", "event_type", "start_date", "end_date", "booking")
    list_filter = ("event_type", "unit")
    date_hierarchy = "start_date"
