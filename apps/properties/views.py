import calendar
from datetime import date

from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import viewsets

from apps.bookings.models import Booking, CalendarEvent
from apps.operations.models import CleaningTask, MaintenanceTask
from .models import Unit
from .api import UnitSerializer


class UnitCardViewSet(viewsets.ViewSet):
    """
    Отдельный ViewSet для карточки юнита (если потребуется отдельный роут).
    Пока логика вынесена в UnitViewSet.card, этот класс может не использоваться.
    """

    def retrieve(self, request, pk=None):
        # Заглушка — основная реализация в UnitViewSet.card
        unit = Unit.objects.get(pk=pk)
        serializer = UnitSerializer(unit)
        return Response(serializer.data)

