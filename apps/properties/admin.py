from django.contrib import admin

from .models import Property, RoomType, Unit, UnitPhoto


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "type",
        "owner",
        "city",
        "district",
        "status",
        "manager",
        "is_active",
        "created_at",
    )
    list_filter = ("type", "status", "city", "is_active")
    search_fields = ("name", "address", "city", "district", "owner__name")


@admin.register(RoomType)
class RoomTypeAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "property",
        "base_capacity",
        "base_area",
        "is_active",
    )
    list_filter = ("property", "is_active")
    search_fields = ("name", "property__name")


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "property",
        "type",
        "floor",
        "area",
        "capacity",
        "status",
        "is_active",
    )
    list_filter = ("type", "status", "property")
    search_fields = ("code", "property__name")


@admin.register(UnitPhoto)
class UnitPhotoAdmin(admin.ModelAdmin):
    list_display = ("id", "unit", "caption", "created_at")
    list_filter = ("unit",)
