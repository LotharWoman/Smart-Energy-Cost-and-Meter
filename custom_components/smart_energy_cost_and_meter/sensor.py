"""Sensoren für Smart Energy Cost & Meter."""
from __future__ import annotations

import calendar
import logging
import math
from datetime import datetime, time, timedelta
from typing import Any

import voluptuous as vol

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_change,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from .calc import calc_increment, parse_float, period_key, period_of, period_start
from .const import (
    ATTR_VALUE,
    BASE_FEE_PERIODS,
    CONF_ENABLED_SENSORS,
    CONF_ENERGY_SENSOR,
    CONF_FEE_TIME,
    CONF_FIXED_PRICE,
    CONF_MONTHLY_FEE,
    CONF_PRICE_SENSOR,
    DATA_STORE,
    DEFAULT_FEE_TIME,
    DOMAIN,
    MAX_FEE_CATCHUP_DAYS,
    SERVICE_SET_VALUE,
)
from .store import SmartEnergyStore

_LOGGER = logging.getLogger(__name__)


def _finite_float(value: Any) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise vol.Invalid("Wert muss eine endliche Zahl sein")
    return number


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    config = {**entry.data, **entry.options}
    store: SmartEnergyStore = hass.data[DOMAIN][DATA_STORE]

    async_add_entities(
        SmartEnergySensor(entry.entry_id, config, store, sensor_type)
        for sensor_type in config.get(CONF_ENABLED_SENSORS, [])
    )

    # Aktion "set_value": Startwert setzen bzw. Zählerstand korrigieren
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SET_VALUE,
        {vol.Required(ATTR_VALUE): vol.All(vol.Coerce(float), _finite_float)},
        "async_set_value",
    )


class SmartEnergySensor(SensorEntity, RestoreEntity):
    """Energie-/Kostenzähler für eine Periode (Summe, Jahr ... Viertelstunde)."""

    _attr_should_poll = False

    def __init__(
        self,
        entry_id: str,
        config: dict,
        store: SmartEnergyStore,
        sensor_type: str,
    ) -> None:
        self._config = config
        self._store = store
        self._sensor_type = sensor_type
        self._period = period_of(sensor_type)
        self._is_cost = sensor_type.endswith("_cost")
        self._source_entity: str | None = config.get(CONF_ENERGY_SENSOR)
        self._fee_time = self._parse_fee_time(config.get(CONF_FEE_TIME))
        self._has_fee = self._is_cost and self._period in BASE_FEE_PERIODS

        readable_name = sensor_type.replace("_", " ").title()
        self._attr_name = f"Smart Energy {readable_name}"
        self._attr_unique_id = f"{entry_id}_{sensor_type}"

        if self._is_cost:
            self._attr_native_unit_of_measurement = "EUR"
            self._attr_device_class = SensorDeviceClass.MONETARY
            self._attr_state_class = SensorStateClass.TOTAL
            self._attr_icon = "mdi:currency-eur"
            self._decimals = 4
        else:
            self._attr_native_unit_of_measurement = "kWh"
            self._attr_device_class = SensorDeviceClass.ENERGY
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
            self._attr_icon = "mdi:lightning-bolt"
            self._decimals = 6

        # --- veränderlicher Zustand (wird in async_added_to_hass wiederhergestellt)
        self._value = 0.0
        self._period_key = period_key(self._period, dt_util.now())
        self._last_source: float | None = None  # letzter GÜLTIGER Eingangswert
        self._last_fee_day = None  # datetime.date der zuletzt verbuchten Grundgebühr

    # ------------------------------------------------------------------ Helfer

    @staticmethod
    def _parse_fee_time(raw: Any) -> time:
        try:
            return time.fromisoformat(str(raw or DEFAULT_FEE_TIME))
        except ValueError:
            _LOGGER.warning(
                "Ungültige Uhrzeit für die Grundgebühr: %r, verwende %s",
                raw,
                DEFAULT_FEE_TIME,
            )
            return time.fromisoformat(DEFAULT_FEE_TIME)

    @property
    def native_value(self) -> float:
        return round(self._value, self._decimals)

    @property
    def last_reset(self) -> datetime | None:
        """Beginn der laufenden Periode.

        Nötig, weil Kosten-Sensoren state_class 'total' haben (Monetary erlaubt
        nichts anderes) und bei Periodenwechsel auf 0 fallen. Mit last_reset
        erkennt Home Assistant das als Reset statt als negativen Verbrauch.
        """
        if self._is_cost and self._period != "total":
            return period_start(self._period, dt_util.now())
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {
            "last_period_key": self._period_key,
            "source_entity": self._source_entity,
            "sensor_type": self._sensor_type,
        }
        if self._is_cost:
            attrs["price_entity"] = self._config.get(CONF_PRICE_SENSOR)
            attrs["fixed_price"] = self._fixed_price()
        return attrs

    def _fixed_price(self) -> float:
        fixed = self._config.get(CONF_FIXED_PRICE)
        return 0.30 if fixed is None else float(fixed)

    def _current_price(self) -> float:
        price = self._fixed_price()
        price_sensor = self._config.get(CONF_PRICE_SENSOR)
        if price_sensor:
            state = self.hass.states.get(price_sensor)
            parsed = parse_float(state.state) if state else None
            if parsed is not None:  # unavailable/unknown -> Festpreis
                price = parsed
        return price

    def _persist(self) -> None:
        self._store.set(
            self._sensor_type,
            {
                "value": self._value,
                "period_key": self._period_key,
                "last_source": self._last_source,
                "source_entity": self._source_entity,
                "last_fee_day": (
                    self._last_fee_day.isoformat() if self._last_fee_day else None
                ),
            },
        )

    # ------------------------------------------------------- Wiederherstellung

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        now = dt_util.now()

        # 1. Eigener Speicher (aktuell + unabhängig von der Entity-Registry)
        restored = self._restore_from_store()
        # 2. Fallback (z. B. erster Start nach dem Update): RestoreEntity
        if not restored:
            restored = await self._restore_from_last_state()
        if not restored:
            _LOGGER.debug("%s: kein gespeicherter Stand, starte bei 0", self.entity_id)

        # Periode wechselte, während HA aus war -> neue Periode beginnt bei 0
        self._roll_period_if_needed(now)

        # Grundgebühr: nachholen, was verpasst wurde (z. B. HA war um 00:30 aus)
        if self._has_fee:
            if self._last_fee_day is None:
                self._last_fee_day = self._initial_fee_day(now)
            self._apply_due_fees(now)

        # Verbrauch während der Ausfallzeit nachholen (Basis stammt aus dem Speicher)
        if self._source_entity:
            self._process_source_state(
                self.hass.states.get(self._source_entity), write=False
            )
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, [self._source_entity], self._handle_source_event
                )
            )

        # Minütlicher Tick: Periodenwechsel zeitgenau + fällige Grundgebühr
        self.async_on_remove(
            async_track_time_change(self.hass, self._handle_tick, second=0)
        )

        self._persist()

    def _restore_from_store(self) -> bool:
        stored = self._store.get(self._sensor_type)
        if not stored:
            return False
        try:
            value = float(stored["value"])
            if not math.isfinite(value):
                raise ValueError("Wert nicht endlich")
            self._value = value
            self._period_key = str(stored.get("period_key") or self._period_key)

            # Basis nur weiterverwenden, wenn es derselbe Eingangssensor ist.
            # Neuer Sensor (z. B. neuer Zähler mit neuer Entity) -> neue Basis.
            if stored.get("source_entity") == self._source_entity:
                self._last_source = parse_float(stored.get("last_source"))
            else:
                self._last_source = None

            fee_day = stored.get("last_fee_day")
            self._last_fee_day = (
                datetime.fromisoformat(fee_day).date() if fee_day else None
            )
        except (KeyError, TypeError, ValueError) as err:
            _LOGGER.warning(
                "%s: gespeicherter Stand unbrauchbar (%s), versuche Wiederherstellung aus letztem Zustand",
                self._sensor_type,
                err,
            )
            self._value = 0.0
            self._last_source = None
            self._last_fee_day = None
            return False
        return True

    async def _restore_from_last_state(self) -> bool:
        last_state = await self.async_get_last_state()
        if last_state is None:
            return False
        value = parse_float(last_state.state)  # unknown/unavailable -> None
        if value is None:
            return False
        self._value = value
        self._period_key = (
            last_state.attributes.get("last_period_key") or self._period_key
        )
        return True

    # ------------------------------------------------------------ Perioden

    def _roll_period_if_needed(self, now: datetime | None = None) -> bool:
        """Neue Periode begonnen? Dann bei 0 anfangen (nie bei 'total')."""
        if self._period == "total":
            return False
        key = period_key(self._period, now or dt_util.now())
        if key == self._period_key:
            return False
        self._period_key = key
        self._value = 0.0
        return True

    # ------------------------------------------------------ Eingangssensor

    @callback
    def _handle_source_event(self, event: Event) -> None:
        self._process_source_state(event.data.get("new_state"))

    @callback
    def _process_source_state(self, state: State | None, write: bool = True) -> None:
        if state is None:
            return
        current = parse_float(state.state)
        if current is None:
            # unavailable/unknown/Text: Basis NICHT anfassen. Der nächste
            # gültige Wert wird gegen den letzten gültigen verglichen, damit
            # der Verbrauch aus der Ausfallzeit nicht verloren geht.
            return

        changed = self._roll_period_if_needed()

        increment_kwh = calc_increment(self._last_source, current)
        if increment_kwh == 0.0 and self._last_source is not None:
            if current - self._last_source > 0:
                _LOGGER.warning(
                    "%s: Eingangssprung %s -> %s kWh nicht gezählt (Zählerwechsel?), neue Basis übernommen",
                    self._sensor_type,
                    self._last_source,
                    current,
                )
            elif current < self._last_source:
                _LOGGER.debug(
                    "%s: Eingangswert %s -> %s, nichts gezählt, neue Basis übernommen",
                    self._sensor_type,
                    self._last_source,
                    current,
                )

        self._last_source = current

        if increment_kwh > 0.0:
            self._value += (
                increment_kwh * self._current_price()
                if self._is_cost
                else increment_kwh
            )
            changed = True

        self._persist()
        if changed and write:
            self.async_write_ha_state()

    # -------------------------------------------------------- Grundgebühr

    def _initial_fee_day(self, now: datetime):
        """Erststart: heutige Gebühr nur 'verpasst', wenn sie noch aussteht."""
        due_today = self._due_datetime(now.date())
        return now.date() if due_today <= now else now.date() - timedelta(days=1)

    def _due_datetime(self, day) -> datetime:
        return datetime.combine(
            day, self._fee_time, tzinfo=dt_util.get_default_time_zone()
        )

    def _apply_due_fees(self, now: datetime) -> bool:
        """Alle fälligen Tagesgebühren verbuchen, die in die AKTUELLE Periode fallen."""
        if not self._has_fee or self._last_fee_day is None:
            return False

        monthly_fee = float(self._config.get(CONF_MONTHLY_FEE) or 0.0)
        today = now.date()
        day = self._last_fee_day + timedelta(days=1)
        earliest = today - timedelta(days=MAX_FEE_CATCHUP_DAYS)
        if day < earliest:
            day = earliest

        current_key = period_key(self._period, now)
        changed = False
        while day <= today:
            due = self._due_datetime(day)
            if due > now:
                break
            # Gebühr gehört nur dann in diesen Sensor, wenn ihr Fälligkeitstag
            # in der laufenden Periode liegt (bei 'total' immer).
            if period_key(self._period, due) == current_key:
                self._value += monthly_fee / calendar.monthrange(day.year, day.month)[1]
                changed = True
            self._last_fee_day = day
            day += timedelta(days=1)
        return changed

    @callback
    def _handle_tick(self, _now: datetime) -> None:
        now = dt_util.now()
        changed = self._roll_period_if_needed(now)
        changed |= self._apply_due_fees(now)
        if changed:
            self._persist()
            self.async_write_ha_state()

    # --------------------------------------------------------------- Aktion

    async def async_set_value(self, value: float) -> None:
        """Aktion set_value: Zählerstand setzen (Startwert/Korrektur)."""
        if not self._is_cost and value < 0:
            raise ServiceValidationError("Energiewerte dürfen nicht negativ sein")

        now = dt_util.now()
        # Erst Periode/Gebühr auf den aktuellen Stand bringen, damit der
        # gesetzte Wert nicht sofort wieder zurückgesetzt oder verändert wird.
        self._roll_period_if_needed(now)
        self._apply_due_fees(now)

        self._value = float(value)
        self._persist()
        self.async_write_ha_state()
