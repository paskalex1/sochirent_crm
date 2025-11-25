from django.contrib import admin

from .models import PriceRecommendation


@admin.register(PriceRecommendation)
class PriceRecommendationAdmin(admin.ModelAdmin):
    list_display = (
        "unit",
        "date",
        "base_price",
        "recommended_price",
        "min_price",
        "max_price",
        "occupancy_7d",
        "occupancy_30d",
        "season",
        "created_at",
    )
    list_filter = ("season", "date", "unit__property")
    search_fields = ("unit__code", "unit__property__name")

