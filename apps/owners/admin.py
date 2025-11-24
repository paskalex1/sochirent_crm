from django.contrib import admin

from .models import Owner


@admin.register(Owner)
class OwnerAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "email", "status", "is_active", "created_at")
    list_filter = ("status", "is_active")
    search_fields = ("name", "phone", "email", "tax_id")

