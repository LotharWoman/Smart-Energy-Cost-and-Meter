DOMAIN = "smart_energy_cost_and_meter"

CONF_ENERGY_SENSOR = "energy_sensor"
CONF_FIXED_PRICE = "fixed_price"
CONF_PRICE_SENSOR = "price_sensor"
CONF_MONTHLY_FEE = "monthly_fee"
CONF_FEE_TIME = "fee_time"
CONF_ENABLED_SENSORS = "enabled_sensors"

SENSOR_TYPES = [
    "total_energy", "total_cost",
    "yearly_energy", "yearly_cost",
    "quarterly_energy", "quarterly_cost",
    "monthly_energy", "monthly_cost",
    "weekly_energy", "weekly_cost",
    "daily_energy", "daily_cost",
    "hourly_energy", "hourly_cost",
    "quarter_hourly_energy", "quarter_hourly_cost"
]