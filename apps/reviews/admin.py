from django.contrib import admin

from .models import ReviewAnalysis


@admin.register(ReviewAnalysis)
class ReviewAnalysisAdmin(admin.ModelAdmin):
    list_display = ("id", "sentiment", "source", "booking", "property", "unit", "created_at")
    list_filter = ("sentiment", "source", "created_at")
    search_fields = ("raw_text",)

