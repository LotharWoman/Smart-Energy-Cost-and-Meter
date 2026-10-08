"""Eigener persistenter Speicher für Zählerstände.

Warum zusätzlich zu RestoreEntity?
- RestoreEntity sichert nur alle 15 min und beim sauberen Herunterfahren und
  verwirft Daten nach 7 Tagen sowie wenn sich die Entity-ID ändert.
- Dieser Speicher liegt in .storage/, ist unabhängig von Config-Entry-ID und
  Entity-Registry und wird bei Entfernen der Integration NICHT gelöscht.
"""
from __future__ import annotations

import copy
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store

from .const import STORAGE_KEY, STORAGE_SAVE_DELAY, STORAGE_VERSION


class SmartEnergyStore:
    """Hält pro Sensortyp den letzten bekannten Stand."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._sensors: dict[str, dict[str, Any]] = {}
        self._save_scheduled = False

    async def async_load(self) -> None:
        data = await self._store.async_load()
        if isinstance(data, dict) and isinstance(data.get("sensors"), dict):
            self._sensors = data["sensors"]

    def get(self, sensor_type: str) -> dict[str, Any] | None:
        item = self._sensors.get(sensor_type)
        return dict(item) if isinstance(item, dict) else None

    @callback
    def set(self, sensor_type: str, item: dict[str, Any]) -> None:
        self._sensors[sensor_type] = item
        self._schedule_save()

    @callback
    def _schedule_save(self) -> None:
        # Nur einmal pro Intervall einplanen: async_delay_save würde bei jedem
        # Aufruf neu starten und bei häufigen Updates nie schreiben.
        if self._save_scheduled:
            return
        self._save_scheduled = True
        self._store.async_delay_save(self._data_to_save, STORAGE_SAVE_DELAY)

    @callback
    def _data_to_save(self) -> dict[str, Any]:
        self._save_scheduled = False
        return {"sensors": copy.deepcopy(self._sensors)}
