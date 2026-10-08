import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector
from .const import (
    DOMAIN,
    CONF_ENERGY_SENSOR,
    CONF_FIXED_PRICE,
    CONF_PRICE_SENSOR,
    CONF_MONTHLY_FEE,
    CONF_FEE_TIME,
    CONF_ENABLED_SENSORS,
    SENSOR_TYPES,
)

class SmartEnergyCostConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="Smart Energy Cost & Meter", data=user_input)

        data_schema = vol.Schema({
            vol.Required(CONF_ENERGY_SENSOR): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="energy")
            ),
            vol.Optional(CONF_FIXED_PRICE, default=0.30): vol.Coerce(float),
            vol.Optional(CONF_PRICE_SENSOR): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Required(CONF_MONTHLY_FEE, default=10.99): vol.Coerce(float),
            vol.Required(CONF_FEE_TIME, default="00:30:00"): str,
            vol.Required(CONF_ENABLED_SENSORS, default=SENSOR_TYPES): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=SENSOR_TYPES,
                    multiple=True,
                    mode=selector.SelectSelectorMode.LIST,
                )
            ),
        })

        return self.async_show_form(step_id="user", data_schema=data_schema)

    @staticmethod
    def async_get_options_flow(config_entry):
        return SmartEnergyCostOptionsFlow()


class SmartEnergyCostOptionsFlow(config_entries.OptionsFlow):
    def __init__(self):
        pass

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = {**self.config_entry.data, **self.config_entry.options}
        price_sensor_val = current.get(CONF_PRICE_SENSOR)

        price_sensor_schema = (
            vol.Optional(CONF_PRICE_SENSOR, default=price_sensor_val)
            if price_sensor_val
            else vol.Optional(CONF_PRICE_SENSOR)
        )

        data_schema = vol.Schema({
            vol.Required(CONF_ENERGY_SENSOR, default=current.get(CONF_ENERGY_SENSOR)): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="energy")
            ),
            vol.Optional(CONF_FIXED_PRICE, default=current.get(CONF_FIXED_PRICE, 0.30)): vol.Coerce(float),
            price_sensor_schema: selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Required(CONF_MONTHLY_FEE, default=current.get(CONF_MONTHLY_FEE, 10.99)): vol.Coerce(float),
            vol.Required(CONF_FEE_TIME, default=current.get(CONF_FEE_TIME, "00:30:00")): str,
            vol.Required(CONF_ENABLED_SENSORS, default=current.get(CONF_ENABLED_SENSORS, SENSOR_TYPES)): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=SENSOR_TYPES,
                    multiple=True,
                    mode=selector.SelectSelectorMode.LIST,
                )
            ),
        })

        return self.async_show_form(step_id="init", data_schema=data_schema)