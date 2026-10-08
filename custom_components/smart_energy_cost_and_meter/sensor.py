import logging
import calendar
from datetime import datetime

from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
    SensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_change
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    CONF_ENERGY_SENSOR,
    CONF_FIXED_PRICE,
    CONF_PRICE_SENSOR,
    CONF_MONTHLY_FEE,
    CONF_FEE_TIME,
    CONF_ENABLED_SENSORS,
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    config = {**entry.data, **entry.options}
    enabled_sensors = config.get(CONF_ENABLED_SENSORS, [])
    
    entities = [SmartEnergySensor(hass, config, entry.entry_id, s_type) for s_type in enabled_sensors]
    async_add_entities(entities)


class SmartEnergySensor(SensorEntity, RestoreEntity):
    def __init__(self, hass: HomeAssistant, config: dict, entry_id: str, sensor_type: str):
        self.hass = hass
        self._config = config
        self._sensor_type = sensor_type
        
        readable_name = sensor_type.replace("_", " ").title()
        self._attr_name = f"Smart Energy {readable_name}"
        self._attr_unique_id = f"{entry_id}_{sensor_type}"
        self._attr_native_value = 0.0
        
        self._is_cost = "cost" in sensor_type
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

        self._state_value = 0.0
        self._last_period_key = self._get_current_period_key()

    @property
    def extra_state_attributes(self):
        """Zusätzliche Attribute für Statuswiederherstellung, Debugging und Dashboard-Templates."""
        attrs = {
            "last_period_key": self._last_period_key,
            "source_entity": self._config.get(CONF_ENERGY_SENSOR),
            "sensor_type": self._sensor_type,
        }
        
        if self._is_cost:
            attrs["price_entity"] = self._config.get(CONF_PRICE_SENSOR)
            attrs["fixed_price"] = float(self._config.get(CONF_FIXED_PRICE, 0.30))
            
        return attrs

    def _get_current_period_key(self):
        now = dt_util.now()
        # "quarter_hourly" MUSS vor "hourly" geprüft werden, da "hourly" sonst fälschlicherweise matcht!
        if "quarter_hourly" in self._sensor_type:
            quarter = now.minute // 15
            return f"{now.strftime('%Y-%m-%d-%H')}-Q{quarter}"
        elif "hourly" in self._sensor_type:
            return now.strftime("%Y-%m-%d-%H")
        elif "daily" in self._sensor_type:
            return now.strftime("%Y-%m-%d")
        elif "weekly" in self._sensor_type:
            return f"{now.year}-W{now.strftime('%V')}"
        elif "monthly" in self._sensor_type:
            return now.strftime("%Y-%m")
        elif "quarterly" in self._sensor_type:
            quarter = (now.month - 1) // 3 + 1
            return f"{now.year}-Q{quarter}"
        elif "yearly" in self._sensor_type:
            return str(now.year)
        return "total"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        
        # Letzten gespeicherten Zustand und Attribut wiederherstellen
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in (None, "unknown", "unavailable"):
            try:
                restored_period = last_state.attributes.get("last_period_key")
                current_period = self._get_current_period_key()
                
                # Wenn sich die Periode während des Offline-Zustands geändert hat, auf 0 zurücksetzen
                if restored_period and restored_period != current_period and "total" not in self._sensor_type:
                    self._state_value = 0.0
                    self._last_period_key = current_period
                else:
                    self._state_value = float(last_state.state)
                    self._last_period_key = restored_period or current_period

                self._attr_native_value = round(self._state_value, self._decimals)
            except ValueError:
                self._state_value = 0.0

        energy_entity = self._config.get(CONF_ENERGY_SENSOR)
        if energy_entity:
            self.async_on_remove(
                async_track_state_change_event(self.hass, [energy_entity], self._async_energy_changed)
            )

        if self._is_cost:
            fee_time_str = self._config.get(CONF_FEE_TIME, "00:30:00")
            t_parts = [int(x) for x in fee_time_str.split(":")]
            self.async_on_remove(
                async_track_time_change(
                    self.hass, 
                    self._async_apply_base_fee, 
                    hour=t_parts[0], 
                    minute=t_parts[1], 
                    second=t_parts[2]
                )
            )

    @callback
    async def _async_energy_changed(self, event):
        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")
        
        if not new_state or not old_state:
            return

        try:
            current_kwh = float(new_state.state)
            old_kwh = float(old_state.state)
            
            if current_kwh < old_kwh:
                diff_kwh = current_kwh
            else:
                diff_kwh = current_kwh - old_kwh
            
            if 0 <= diff_kwh < 50:
                current_period = self._get_current_period_key()
                if current_period != self._last_period_key and "total" not in self._sensor_type:
                    self._state_value = 0.0
                    self._last_period_key = current_period

                price_sensor = self._config.get(CONF_PRICE_SENSOR)
                price = float(self._config.get(CONF_FIXED_PRICE, 0.30))
                
                if price_sensor:
                    p_state = self.hass.states.get(price_sensor)
                    if p_state:
                        try:
                            price = float(p_state.state)
                        except ValueError:
                            pass

                increment = (diff_kwh * price) if self._is_cost else diff_kwh
                self._state_value += increment
                self._attr_native_value = round(self._state_value, self._decimals)
                self.async_write_ha_state()
        except ValueError:
            pass

    async def _async_apply_base_fee(self, *args):
        if not self._is_cost:
            return
            
        monthly_fee = float(self._config.get(CONF_MONTHLY_FEE, 0.0))
        now = dt_util.now()
        
        days_in_month = calendar.monthrange(now.year, now.month)[1]
        daily_fee = monthly_fee / days_in_month

        if any(period in self._sensor_type for period in ["daily", "total", "monthly", "quarterly", "yearly"]):
            self._state_value += daily_fee
            self._attr_native_value = round(self._state_value, self._decimals)
            self.async_write_ha_state()