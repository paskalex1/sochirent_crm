from rest_framework import serializers, viewsets
from rest_framework.permissions import IsAuthenticatedOrReadOnly

from .models import Owner


class OwnerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Owner
        fields = [
            "id",
            "name",
            "phone",
            "email",
            "notes",
            "tax_id",
            "status",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class OwnerViewSet(viewsets.ModelViewSet):
    queryset = Owner.objects.all().order_by("name")
    serializer_class = OwnerSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

