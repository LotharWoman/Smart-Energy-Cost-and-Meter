import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    DEFAULT_FEE_TIME,
    DOMAIN,
    CONF_ENERGY_SENSOR,
    CONF_FIXED_PRICE,
    CONF_PRICE_SENSOR,
    CONF_MONTHLY_FEE,
    CONF_FEE_TIME,
    CONF_ENABLED_SENSORS,
    SENSOR_TYPES,
)


def _sensor_selector() -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=SENSOR_TYPES,
            multiple=True,
            mode=selector.SelectSelectorMode.LIST,
        )
    )


class SmartEnergyCostConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Smart Energy Cost & Meter."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is not None:
            return self.async_create_entry(
                title="Smart Energy Cost & Meter", data=user_input
            )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_ENERGY_SENSOR): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor", device_class="energy"
                    )
                ),
                vol.Optional(CONF_FIXED_PRICE, default=0.30): vol.Coerce(float),
                vol.Optional(CONF_PRICE_SENSOR): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(CONF_MONTHLY_FEE, default=10.99): vol.Coerce(float),
                vol.Required(
                    CONF_FEE_TIME, default=DEFAULT_FEE_TIME
                ): selector.TimeSelector(),
                vol.Required(
                    CONF_ENABLED_SENSORS, default=SENSOR_TYPES
                ): _sensor_selector(),
            }
        )

        return self.async_show_form(step_id="user", data_schema=data_schema)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        # self.config_entry stellt die Basisklasse selbst bereit
        return SmartEnergyCostOptionsFlow()


class SmartEnergyCostOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Smart Energy Cost & Meter."""

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            data = dict(user_input)
            # Ein im Formular geleertes Feld fehlt in user_input. Ohne expliziten
            # Eintrag würde der alte Wert aus entry.data wieder durchscheinen.
            data.setdefault(CONF_PRICE_SENSOR, None)
            return self.async_create_entry(title="", data=data)

        current = {**self.config_entry.data, **self.config_entry.options}

        # suggested_value statt default: nur so lässt sich das optionale
        # Preis-Sensor-Feld im Dialog auch wieder leeren.
        schema = vol.Schema(
            {
                vol.Required(CONF_ENERGY_SENSOR): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor", device_class="energy"
                    )
                ),
                vol.Optional(CONF_FIXED_PRICE): vol.Coerce(float),
                vol.Optional(CONF_PRICE_SENSOR): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(CONF_MONTHLY_FEE): vol.Coerce(float),
                vol.Required(CONF_FEE_TIME): selector.TimeSelector(),
                vol.Required(CONF_ENABLED_SENSORS): _sensor_selector(),
            }
        )
        suggestions = {
            CONF_ENERGY_SENSOR: current.get(CONF_ENERGY_SENSOR),
            CONF_FIXED_PRICE: current.get(CONF_FIXED_PRICE, 0.30),
            CONF_PRICE_SENSOR: current.get(CONF_PRICE_SENSOR),
            CONF_MONTHLY_FEE: current.get(CONF_MONTHLY_FEE, 10.99),
            CONF_FEE_TIME: current.get(CONF_FEE_TIME, DEFAULT_FEE_TIME),
            CONF_ENABLED_SENSORS: current.get(CONF_ENABLED_SENSORS, SENSOR_TYPES),
        }

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(schema, suggestions),
        )
