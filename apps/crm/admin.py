from django.contrib import admin
from .models import Pipeline, Stage, Lead, Deal

@admin.register(Pipeline)
class PipelineAdmin(admin.ModelAdmin):
    list_display = ("name","code","is_active")
    search_fields = ("name","code")

@admin.register(Stage)
class StageAdmin(admin.ModelAdmin):
    list_display = ("name","pipeline","order","is_won","is_lost")
    list_filter = ("pipeline","is_won","is_lost")
    ordering = ("pipeline","order")

@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ("full_name","phone","email","source","status","responsible","created_at")
    list_filter = ("status","source")
    search_fields = ("full_name","phone","email")
    autocomplete_fields = ("responsible",)

@admin.register(Deal)
class DealAdmin(admin.ModelAdmin):
    list_display = ("title","pipeline","stage","value","responsible","probability","is_closed")
    list_filter = ("pipeline","stage","is_closed")
    search_fields = ("title",)
    autocomplete_fields = ("lead","responsible")
