from django.shortcuts import get_object_or_404
from rest_framework import serializers, viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from django_filters.rest_framework import DjangoFilterBackend

from .models import Lead, Deal, Pipeline, Stage

from rest_framework.permissions import IsAuthenticatedOrReadOnly
from .permissions import LeadCreatePermission

# ---------- Serializers ----------
class PipelineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pipeline
        fields = ["id", "name", "code", "is_active"]

class StageSerializer(serializers.ModelSerializer):
    pipeline = PipelineSerializer(read_only=True)
    pipeline_id = serializers.PrimaryKeyRelatedField(
        queryset=Pipeline.objects.all(), source="pipeline", write_only=True
    )
    class Meta:
        model = Stage
        fields = ["id", "name", "code", "order", "is_won", "is_lost", "pipeline", "pipeline_id"]

class LeadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lead
        fields = [
            "id", "full_name", "phone", "email", "source", "status",
            "responsible", "notes", "created_at",
        ]
        read_only_fields = ["id", "created_at"]

class DealSerializer(serializers.ModelSerializer):
    pipeline = PipelineSerializer(read_only=True)
    stage = StageSerializer(read_only=True)

    # write-only поля для установки по id
    pipeline_id = serializers.PrimaryKeyRelatedField(
        queryset=Pipeline.objects.all(), source="pipeline", write_only=True
    )
    stage_id = serializers.PrimaryKeyRelatedField(
        queryset=Stage.objects.all(), source="stage", write_only=True
    )
    lead_id = serializers.PrimaryKeyRelatedField(
        queryset=Lead.objects.all(), source="lead", write_only=True, required=False, allow_null=True
    )

    class Meta:
        model = Deal
        fields = [
            "id", "title", "lead", "lead_id",
            "pipeline", "pipeline_id",
            "stage", "stage_id",
            "value", "responsible", "probability",
            "expected_close_date", "created_at", "updated_at", "is_closed",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

# ---------- ViewSets ----------
class PipelineViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Pipeline.objects.all()
    serializer_class = PipelineSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

class StageViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Stage.objects.select_related("pipeline").all()
    serializer_class = StageSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["pipeline__code"]
    permission_classes = [IsAuthenticatedOrReadOnly]

class LeadViewSet(viewsets.ModelViewSet):
    queryset = Lead.objects.all().order_by("-id")
    serializer_class = LeadSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["status", "source"]

    def get_permissions(self):
        # 1) Создание разрешено по X-API-Key или авторизованному пользователю
        if self.action == "create":
            return [LeadCreatePermission()]
        # 2) Все остальные действия — только для авторизованных
        return [IsAuthenticatedOrReadOnly()]

class DealViewSet(viewsets.ModelViewSet):
    queryset = Deal.objects.select_related("pipeline", "stage", "lead").all().order_by("-id")
    serializer_class = DealSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["pipeline__code", "stage__code", "responsible"]
    permission_classes = [IsAuthenticatedOrReadOnly]

    @action(methods=["post"], detail=True, url_path="move")
    def move(self, request, pk=None):
        """
        Move deal to a new stage within its pipeline.
        Body: {"stage_id": <int>}
        """
        deal = self.get_object()
        stage_id = request.data.get("stage_id")
        if not stage_id:
            return Response({"detail": "stage_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        stage = get_object_or_404(Stage, pk=stage_id, pipeline=deal.pipeline)
        deal.stage = stage
        deal.save(update_fields=["stage", "updated_at"])
        return Response(self.get_serializer(deal).data, status=status.HTTP_200_OK)
