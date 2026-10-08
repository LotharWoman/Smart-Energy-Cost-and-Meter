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

PLATFORMS = ["sensor"]

DEFAULT_FEE_TIME = "00:30:00"

# Perioden, bei denen die anteilige tägliche Grundgebühr aufgeschlagen wird
# (nicht bei Stunde/Viertelstunde)
BASE_FEE_PERIODS = ("daily", "weekly", "monthly", "quarterly", "yearly", "total")

# Aktion zum manuellen Setzen von Startwerten / Korrekturen
SERVICE_SET_VALUE = "set_value"
ATTR_VALUE = "value"

# --- Zähllogik ---------------------------------------------------------
# Größter Zuwachs (kWh) zwischen zwei gültigen Messwerten des Eingangssensors,
# der noch als echter Verbrauch gewertet wird. Alles darüber (z. B. neuer
# Zähler mit hohem Startwert) wird nur als neue Basis übernommen.
MAX_DELTA_KWH = 50.0
# Fällt der Eingangswert unter diesen Anteil des letzten Werts, gilt das als
# Zählerreset/-wechsel (gleiche Schwelle wie bei Home Assistant Statistiken).
# Kleinere Rückgänge sind Rundungs-/Korrekturrauschen und zählen nicht.
RESET_RATIO = 0.9
# Maximal so viele verpasste Tage Grundgebühr werden nachgeholt
MAX_FEE_CATCHUP_DAYS = 400

# --- Persistenz --------------------------------------------------------
# Eigener Speicher in .storage, unabhängig von Config-Entry-ID und
# Entity-Registry -> übersteht Neuinstallation der Integration.
STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.sensor_values"
STORAGE_SAVE_DELAY = 10  # Sekunden

DATA_STORE = "store"
