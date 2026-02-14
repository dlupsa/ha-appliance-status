"""Binary sensor platform for Appliance Status Monitor."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.device_registry import DeviceInfo

from .const import CONF_APPLIANCE_NAME, DOMAIN
from .coordinator import ApplianceMonitor


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Appliance Status binary sensor."""
    monitor: ApplianceMonitor = entry.runtime_data
    async_add_entities([ApplianceRunningBinarySensor(monitor, entry)])


class ApplianceRunningBinarySensor(BinarySensorEntity):
    """Binary sensor indicating if the appliance is running."""

    _attr_has_entity_name = True
    _attr_translation_key = "appliance_running"
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_icon = "mdi:play-circle"

    def __init__(
        self, monitor: ApplianceMonitor, entry: ConfigEntry
    ) -> None:
        """Initialize the binary sensor."""
        self._monitor = monitor

        self._attr_unique_id = f"{entry.entry_id}_running"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data[CONF_APPLIANCE_NAME],
            manufacturer="Appliance Status Monitor",
            model="Power Monitor",
        )

    @property
    def is_on(self) -> bool:
        """Return True if the appliance is running."""
        return self._monitor.is_running

    async def async_added_to_hass(self) -> None:
        """Register update callback."""
        self._monitor.register_update_callback(self._handle_update)

    async def async_will_remove_from_hass(self) -> None:
        """Unregister update callback."""
        self._monitor.unregister_update_callback(self._handle_update)

    @callback
    def _handle_update(self) -> None:
        """Handle state update from monitor."""
        self.async_write_ha_state()
