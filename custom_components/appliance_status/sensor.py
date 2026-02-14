"""Sensor platform for Appliance Status Monitor."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorEntity,
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
    """Set up Appliance Status sensor."""
    monitor: ApplianceMonitor = entry.runtime_data
    async_add_entities([ApplianceStatusSensor(monitor, entry)])


class ApplianceStatusSensor(SensorEntity):
    """Sensor showing the current appliance status."""

    _attr_has_entity_name = True
    _attr_translation_key = "appliance_status"
    _attr_icon = "mdi:state-machine"

    def __init__(
        self, monitor: ApplianceMonitor, entry: ConfigEntry
    ) -> None:
        """Initialize the sensor."""
        self._monitor = monitor
        slug = monitor.appliance_name.lower().replace(" ", "_").replace("-", "_")

        self._attr_unique_id = f"{entry.entry_id}_status"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data[CONF_APPLIANCE_NAME],
            manufacturer="Appliance Status Monitor",
            model="Power Monitor",
            entry_type=None,
        )

    @property
    def native_value(self) -> str:
        """Return the current status."""
        return self._monitor.state

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional attributes."""
        attrs = {
            "power_entity": self._monitor.power_entity,
            "current_power": self._monitor.current_power,
            "internal_state": self._monitor.internal_state,
        }
        if self._monitor.last_started:
            attrs["last_started"] = self._monitor.last_started.isoformat()
        if self._monitor.last_completed:
            attrs["last_completed"] = self._monitor.last_completed.isoformat()
        if self._monitor.cycle_duration is not None:
            attrs["cycle_duration"] = round(self._monitor.cycle_duration)
        attrs["cycles_today"] = self._monitor.cycles_today
        return attrs

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
