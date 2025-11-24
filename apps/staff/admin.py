from django.contrib import admin

from .models import Staff


@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "user",
        "role",
        "department",
        "position",
        "is_active_employee",
        "created_at",
    )
    list_filter = ("role", "department", "is_active_employee")
    search_fields = ("full_name", "user__username", "user__email", "phone", "email")
    filter_horizontal = ("properties",)

