"""The Appliance Status Monitor integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS
from .coordinator import ApplianceMonitor

_LOGGER = logging.getLogger(__name__)

type ApplianceStatusConfigEntry = ConfigEntry[ApplianceMonitor]


async def async_setup_entry(
    hass: HomeAssistant, entry: ApplianceStatusConfigEntry
) -> bool:
    """Set up Appliance Status Monitor from a config entry."""
    monitor = ApplianceMonitor(hass, entry)
    entry.runtime_data = monitor

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Start monitoring after platforms are set up
    await monitor.async_start()

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ApplianceStatusConfigEntry
) -> bool:
    """Unload a config entry."""
    monitor: ApplianceMonitor = entry.runtime_data
    monitor.async_stop()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
