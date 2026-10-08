"""Reine Rechenlogik (ohne Home-Assistant-Abhängigkeit, daher einzeln testbar)."""
from __future__ import annotations

import math
from datetime import datetime, timedelta

from .const import MAX_DELTA_KWH, RESET_RATIO


def period_of(sensor_type: str) -> str:
    """'quarter_hourly_energy' -> 'quarter_hourly', 'total_cost' -> 'total'."""
    return sensor_type.rsplit("_", 1)[0]


def period_key(period: str, now: datetime) -> str:
    """Schlüssel der Periode, in der `now` liegt. Ändert er sich, beginnt eine neue Periode."""
    if period == "quarter_hourly":
        # %z: unterscheidet die doppelte Stunde bei der Zeitumstellung
        return f"{now:%Y-%m-%d-%H%z}-Q{now.minute // 15}"
    if period == "hourly":
        return f"{now:%Y-%m-%d-%H%z}"
    if period == "daily":
        return f"{now:%Y-%m-%d}"
    if period == "weekly":
        iso = now.isocalendar()  # ISO-Jahr, nicht Kalenderjahr (Jahreswechsel!)
        return f"{iso.year}-W{iso.week:02d}"
    if period == "monthly":
        return f"{now:%Y-%m}"
    if period == "quarterly":
        return f"{now.year}-Q{(now.month - 1) // 3 + 1}"
    if period == "yearly":
        return str(now.year)
    return "total"


def period_start(period: str, now: datetime) -> datetime:
    """Beginn der Periode, in der `now` liegt (für last_reset)."""
    day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "quarter_hourly":
        return now.replace(minute=now.minute // 15 * 15, second=0, microsecond=0)
    if period == "hourly":
        return now.replace(minute=0, second=0, microsecond=0)
    if period == "daily":
        return day
    if period == "weekly":
        return day - timedelta(days=now.weekday())  # Montag 00:00
    if period == "monthly":
        return day.replace(day=1)
    if period == "quarterly":
        return day.replace(month=(now.month - 1) // 3 * 3 + 1, day=1)
    if period == "yearly":
        return day.replace(month=1, day=1)
    return day.replace(year=1970, month=1, day=1)  # "total": nie zurückgesetzt


def parse_float(raw) -> float | None:
    """Zustand -> float. None bei unavailable/unknown/Text/NaN/inf."""
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def calc_increment(last: float | None, current: float) -> float:
    """Verbrauchszuwachs in kWh zwischen letztem und aktuellem gültigem Zählerstand.

    Rückgabe 0.0 bedeutet: nichts zählen (der Aufrufer übernimmt `current`
    trotzdem als neue Basis).
    """
    if last is None:
        return 0.0  # erste Messung: nur Basis merken

    if current >= last:
        delta = current - last
        # Riesensprung nach oben (neuer Zähler mit hohem Startwert, Fehlwert)
        return delta if delta <= MAX_DELTA_KWH else 0.0

    if current >= last * RESET_RATIO:
        return 0.0  # kleiner Rückgang: Rauschen/Korrektur, kein Verbrauch

    # Deutlicher Rückgang = Zähler wurde zurückgesetzt/getauscht. Der neue
    # Zähler zeigt dann den Verbrauch seit seinem Start.
    return current if 0.0 <= current <= MAX_DELTA_KWH else 0.0
