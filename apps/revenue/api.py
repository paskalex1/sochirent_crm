from datetime import date

from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.properties.models import Unit
from apps.staff.permissions import IsRevenueRole
from .models import PriceRecommendation
from .services import suggest_price_for_unit_on_date


class PriceSuggestionInputSerializer(serializers.Serializer):
    unit_id = serializers.IntegerField()
    date = serializers.DateField()


class PriceSuggestionView(APIView):
    """
    GET /api/v1/revenue/price-suggestion/?unit_id=&date=YYYY-MM-DD
    """

    permission_classes = [IsAuthenticated, IsRevenueRole]

    def get(self, request, *args, **kwargs):
        serializer = PriceSuggestionInputSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        unit = get_object_or_404(Unit, pk=data["unit_id"])
        target_date: date = data["date"]

        suggestion = suggest_price_for_unit_on_date(unit, target_date)

        payload = {
            "unit_id": unit.id,
            "date": target_date.isoformat(),
            **suggestion,
        }
        return Response(payload)


class PriceRecommendationQuerySerializer(serializers.Serializer):
    unit_id = serializers.IntegerField()
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)


class PriceRecommendationSerializer(serializers.ModelSerializer):
    unit_id = serializers.IntegerField(source="unit_id", read_only=True)

    class Meta:
        model = PriceRecommendation
        fields = [
            "id",
            "unit_id",
            "date",
            "base_price",
            "recommended_price",
            "min_price",
            "max_price",
            "occupancy_7d",
            "occupancy_30d",
            "season",
            "notes",
        ]


class PriceRecommendationListView(APIView):
    """
    GET /api/v1/revenue/price-recommendations/?unit_id=&date_from=&date_to=
    """

    permission_classes = [IsAuthenticated, IsRevenueRole]

    def get(self, request, *args, **kwargs):
        serializer = PriceRecommendationQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        unit_id = data["unit_id"]
        qs = PriceRecommendation.objects.filter(unit_id=unit_id)

        date_from = data.get("date_from")
        date_to = data.get("date_to")

        if date_from and date_to:
            qs = qs.filter(date__range=(date_from, date_to))
        elif date_from:
            qs = qs.filter(date__gte=date_from)
        elif date_to:
            qs = qs.filter(date__lte=date_to)

        qs = qs.order_by("date", "created_at")

        out = PriceRecommendationSerializer(qs, many=True)
        return Response(out.data)

