from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DATA_STORE, DOMAIN, PLATFORMS
from .store import SmartEnergyStore


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Integration laden."""
    domain_data = hass.data.setdefault(DOMAIN, {})

    # Der Speicher wird nur EINMAL geladen und bleibt über Reloads im Speicher
    # (sonst könnte ein Reload noch nicht geschriebene Werte mit dem älteren
    # Dateiinhalt überschreiben). Er gehört der Integration, nicht dem Entry,
    # und wird beim Entfernen des Entries bewusst nicht gelöscht.
    if DATA_STORE not in domain_data:
        store = SmartEnergyStore(hass)
        await store.async_load()
        domain_data[DATA_STORE] = store

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Integration entladen."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Wird aufgerufen, wenn Einstellungen im laufenden Betrieb geändert werden."""
    await hass.config_entries.async_reload(entry.entry_id)
