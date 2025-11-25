from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.bookings.models import Booking
from apps.operations.models import MaintenanceTask
from apps.reviews.models import ReviewAnalysis
from apps.staff.permissions import IsAIRole
from .services import AIClient


class ReviewAnalysisSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReviewAnalysis
        fields = [
            "id",
            "booking",
            "property",
            "unit",
            "source",
            "raw_text",
            "sentiment",
            "categories",
            "summary",
            "suggestions",
            "created_at",
            "analyzed_at",
        ]
        read_only_fields = [
            "id",
            "sentiment",
            "categories",
            "summary",
            "suggestions",
            "created_at",
            "analyzed_at",
        ]


class ReviewAnalyzeInputSerializer(serializers.Serializer):
    booking_id = serializers.IntegerField(required=False)
    property_id = serializers.IntegerField(required=False)
    unit_id = serializers.IntegerField(required=False)
    source = serializers.CharField(max_length=50)
    text = serializers.CharField()


class ReviewAnalyzeView(APIView):
    """
    POST /api/v1/ai/reviews/analyze/
    """

    permission_classes = [IsAuthenticated, IsAIRole]

    def post(self, request, *args, **kwargs):
        serializer = ReviewAnalyzeInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        booking = None
        prop = None
        unit = None

        booking_id = data.get("booking_id")
        if booking_id is not None:
            booking = get_object_or_404(Booking, pk=booking_id)
            prop = booking.property
            unit = booking.unit

        property_id = data.get("property_id")
        if property_id is not None and prop is None:
            from apps.properties.models import Property  # локальный импорт

            prop = get_object_or_404(Property, pk=property_id)

        unit_id = data.get("unit_id")
        if unit_id is not None and unit is None:
            from apps.properties.models import Unit  # локальный импорт

            unit = get_object_or_404(Unit, pk=unit_id)

        text = data["text"]
        source = data["source"]

        client = AIClient()
        ai_result = client.analyze_review(text)

        review = ReviewAnalysis.objects.create(
            booking=booking,
            property=prop,
            unit=unit,
            source=source,
            raw_text=text,
            sentiment=ai_result.get("sentiment", "neutral"),
            categories=ai_result.get("categories", []),
            summary=ai_result.get("summary", ""),
            suggestions=ai_result.get("suggestions", ""),
        )

        out = ReviewAnalysisSerializer(review)
        return Response(out.data, status=status.HTTP_201_CREATED)


class MaintenanceTaskAIBlockSerializer(serializers.Serializer):
    ai_problem_type = serializers.CharField()
    ai_urgency = serializers.CharField()
    ai_recommendation = serializers.CharField(allow_blank=True)
    ai_last_analyzed_at = serializers.DateTimeField()


class MaintenanceTaskAIAnalyzeView(APIView):
    """
    POST /api/v1/ai/tasks/maintenance/{id}/analyze/
    """

    permission_classes = [IsAuthenticated, IsAIRole]

    def post(self, request, pk: int, *args, **kwargs):
        task = get_object_or_404(MaintenanceTask, pk=pk)

        text_parts = [task.title or ""]
        if task.description:
            text_parts.append(task.description)
        text = "\n\n".join(text_parts).strip()

        if not text:
            return Response(
                {"detail": "У задачи отсутствует текст для анализа."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        client = AIClient()
        ai_result = client.analyze_task(text)

        from django.utils import timezone

        task.ai_problem_type = ai_result.get("problem_type", "")
        task.ai_urgency = ai_result.get("urgency", "")
        task.ai_recommendation = ai_result.get("recommendation", "")
        task.ai_last_analyzed_at = timezone.now()
        task.save(
            update_fields=[
                "ai_problem_type",
                "ai_urgency",
                "ai_recommendation",
                "ai_last_analyzed_at",
                "updated_at",
            ]
        )

        payload = {
            "ai_problem_type": task.ai_problem_type,
            "ai_urgency": task.ai_urgency,
            "ai_recommendation": task.ai_recommendation,
            "ai_last_analyzed_at": task.ai_last_analyzed_at,
        }

        out = MaintenanceTaskAIBlockSerializer(payload)
        return Response(out.data)

