from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, Optional

from apps.bookings.models import Booking, RatePlan
from apps.properties.models import Unit
from .models import PriceRecommendation


@dataclass
class PriceSuggestion:
    base_price: Decimal
    recommended_price: Decimal
    min_price: Decimal
    max_price: Decimal
    occupancy_7d: Optional[float]
    occupancy_30d: Optional[float]
    season: str
    notes: str


def _detect_season(target_date: date) -> str:
    """
    Определяет сезон по месяцу:
      - high: июнь, июль, август, сентябрь;
      - low: декабрь, январь, февраль;
      - shoulder: остальные.
    """
    month = target_date.month
    if month in (12, 1, 2):
        return "low"
    if month in (6, 7, 8, 9):
        return "high"
    return "shoulder"


def _calc_occupancy_for_period(unit: Unit, end_date: date, days: int) -> Optional[float]:
    """
    Считает загрузку по объекту unit.property за период [end_date - days, end_date):
      occupied_nights / (units_count * days).
    """
    start_date = end_date - timedelta(days=days)
    prop = unit.property

    units_qs = prop.units.filter(
        status=Unit.Status.ACTIVE,
        is_active=True,
    )
    units_count = units_qs.count()
    if units_count == 0 or days <= 0:
        return None

    bookings_qs = Booking.objects.filter(
        property=prop,
        check_in__lt=end_date,
        check_out__gt=start_date,
    )

    occupied_nights = 0
    for booking in bookings_qs:
        start = max(booking.check_in, start_date)
        end = min(booking.check_out, end_date)
        nights = (end - start).days
        if nights > 0:
            occupied_nights += nights

    denominator = units_count * days
    if denominator <= 0:
        return None

    return float(occupied_nights / denominator)


def suggest_price_for_unit_on_date(unit: Unit, target_date: date) -> Dict:
    """
    Возвращает и логирует рекомендацию цены для юнита на дату.
    """
    prop = unit.property

    # 1. Базовая цена из RatePlan.
    rate_plan: Optional[RatePlan] = (
        RatePlan.objects.filter(property=prop, is_active=True).order_by("id").first()
    )
    if rate_plan is None or rate_plan.base_price is None:
        base_price = Decimal("0.00")
    else:
        base_price = rate_plan.base_price

    # 2. Загрузка за периоды.
    occupancy_7d = _calc_occupancy_for_period(unit, target_date, 7)
    occupancy_30d = _calc_occupancy_for_period(unit, target_date, 30)

    # 3. Сезон.
    season = _detect_season(target_date)

    # 4. Коэффициент на основе загрузки.
    coeff = Decimal("1.00")

    if base_price > 0 and occupancy_30d is not None:
        occ30 = occupancy_30d
        if occ30 >= 0.8:
            coeff *= Decimal("1.15")
        elif occ30 >= 0.6:
            coeff *= Decimal("1.05")
        elif occ30 <= 0.3:
            coeff *= Decimal("0.90")

    # Дополнительный коэффициент для high‑сезона.
    if base_price > 0 and season == "high":
        coeff *= Decimal("1.10")

    # 5. Диапазон и обрезка.
    if base_price > 0:
        min_price = (base_price * Decimal("0.7")).quantize(Decimal("0.01"))
        max_price = (base_price * Decimal("1.5")).quantize(Decimal("0.01"))
        raw_recommended = (base_price * coeff).quantize(Decimal("0.01"))
        recommended_price = max(min_price, min(max_price, raw_recommended))
    else:
        min_price = base_price
        max_price = base_price
        raw_recommended = base_price
        recommended_price = base_price

    # 6. Формирование человеко-читабельного пояснения.
    notes_lines = []
    notes_lines.append(f"Базовая цена: {base_price} ₽.")

    if occupancy_30d is not None and base_price > 0:
        occ_percent = f"{occupancy_30d * 100:.0f}%"
        if occupancy_30d >= 0.8:
            notes_lines.append(
                f"Загрузка за 30 дней: {occ_percent}. Применена надбавка +15%."
            )
        elif occupancy_30d >= 0.6:
            notes_lines.append(
                f"Загрузка за 30 дней: {occ_percent}. Применена надбавка +5%."
            )
        elif occupancy_30d <= 0.3:
            notes_lines.append(
                f"Загрузка за 30 дней: {occ_percent}. Применена скидка -10%."
            )
        else:
            notes_lines.append(f"Загрузка за 30 дней: {occ_percent}. Корректировка не применена.")

    season_ru = {
        "high": "высокий",
        "low": "низкий",
        "shoulder": "межсезонье",
    }.get(season, season)

    if base_price > 0 and season == "high":
        notes_lines.append(f"Сезон: {season_ru}. Дополнительная надбавка +10%.")
    else:
        notes_lines.append(f"Сезон: {season_ru}.")

    if base_price > 0 and recommended_price != raw_recommended:
        notes_lines.append(
            f"Цена ограничена диапазоном {min_price}–{max_price} ₽."
        )

    notes_lines.append(f"Итоговая рекомендованная цена: {recommended_price} ₽.")

    notes = " ".join(notes_lines)

    recommendation = PriceRecommendation.objects.create(
        unit=unit,
        date=target_date,
        base_price=base_price,
        recommended_price=recommended_price,
        min_price=min_price,
        max_price=max_price,
        occupancy_7d=occupancy_7d,
        occupancy_30d=occupancy_30d,
        season=season,
        notes=notes,
    )

    return {
        "base_price": float(recommendation.base_price),
        "recommended_price": float(recommendation.recommended_price),
        "min_price": float(recommendation.min_price),
        "max_price": float(recommendation.max_price),
        "occupancy_7d": recommendation.occupancy_7d,
        "occupancy_30d": recommendation.occupancy_30d,
        "season": recommendation.season,
        "notes": recommendation.notes,
    }
