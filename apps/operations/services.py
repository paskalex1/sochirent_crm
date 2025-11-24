from typing import Iterable

from apps.bookings.models import Booking
from apps.operations.models import CleaningTask, TaskBaseModel
from apps.properties.models import Property


RELEVANT_PROPERTY_TYPES: Iterable[str] = [
    Property.PropertyType.RESIDENTIAL_SHORT,
    Property.PropertyType.HOTEL,
]


def sync_cleaning_tasks_for_booking(booking: Booking) -> None:
    """
    Создаёт/обновляет задачи клининга для бронирования.

    Логика:
    - срабатывает только для объектов с типом residential_short / hotel;
    - и только если статус брони подтверждён / заезд / выезд;
    - создаёт предзаездную и послезаездную уборку, если их ещё нет;
    - обновляет дедлайны задач по датам check_in/check_out.
    """
    if booking.property.type not in RELEVANT_PROPERTY_TYPES:
        return

    if booking.status not in {
        Booking.Status.CONFIRMED,
        Booking.Status.CHECKIN,
        Booking.Status.CHECKOUT,
    }:
        return

    if not booking.check_in or not booking.check_out:
        return

    # Предзаездная уборка.
    pre_tasks = CleaningTask.objects.filter(
        booking=booking,
        unit=booking.unit,
        property=booking.property,
        is_pre_arrival=True,
    )
    if not pre_tasks.exists():
        pre_task = CleaningTask.objects.create(
            title=f"Уборка перед заездом для брони #{booking.id}",
            description="Автоматически созданная предзаездная уборка.",
            property=booking.property,
            unit=booking.unit,
            booking=booking,
            is_pre_arrival=True,
            requires_quality_inspection=True,
        )
        pre_tasks = CleaningTask.objects.filter(pk=pre_task.pk)

    for t in pre_tasks:
        if t.deadline != booking.check_in:
            t.deadline = booking.check_in
            t.status = t.status or TaskBaseModel.Status.NEW
            t.save(update_fields=["deadline", "status", "updated_at"])

    # Послезаездная уборка.
    post_tasks = CleaningTask.objects.filter(
        booking=booking,
        unit=booking.unit,
        property=booking.property,
        is_post_departure=True,
    )
    if not post_tasks.exists():
        post_task = CleaningTask.objects.create(
            title=f"Уборка после выезда для брони #{booking.id}",
            description="Автоматически созданная послезаселения уборка.",
            property=booking.property,
            unit=booking.unit,
            booking=booking,
            is_post_departure=True,
            requires_quality_inspection=True,
        )
        post_tasks = CleaningTask.objects.filter(pk=post_task.pk)

    for t in post_tasks:
        if t.deadline != booking.check_out:
            t.deadline = booking.check_out
            t.status = t.status or TaskBaseModel.Status.NEW
            t.save(update_fields=["deadline", "status", "updated_at"])

