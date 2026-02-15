"""Sensor platform for Appliance Status Monitor."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfPower, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.util import dt as dt_util

from .const import CONF_APPLIANCE_NAME, DOMAIN
from .coordinator import ApplianceMonitor


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Appliance Status sensors."""
    monitor: ApplianceMonitor = entry.runtime_data
    async_add_entities([
        ApplianceStatusSensor(monitor, entry),
        AppliancePowerSensor(monitor, entry),
        ApplianceCycleDurationSensor(monitor, entry),
        ApplianceCyclesTodaySensor(monitor, entry),
        ApplianceCycleEnergySensor(monitor, entry),
    ])


class ApplianceBaseSensor(SensorEntity):
    """Base class for appliance sensors with shared device info and update callback."""

    _attr_has_entity_name = True

    def __init__(
        self, monitor: ApplianceMonitor, entry: ConfigEntry
    ) -> None:
        """Initialize the sensor."""
        self._monitor = monitor
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data[CONF_APPLIANCE_NAME],
            manufacturer="Appliance Status Monitor",
            model="Power Monitor",
        )

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


class ApplianceStatusSensor(ApplianceBaseSensor):
    """Sensor showing the current appliance status."""

    _attr_translation_key = "appliance_status"
    _attr_icon = "mdi:state-machine"

    def __init__(
        self, monitor: ApplianceMonitor, entry: ConfigEntry
    ) -> None:
        """Initialize the sensor."""
        super().__init__(monitor, entry)
        self._attr_unique_id = f"{entry.entry_id}_status"

    @property
    def native_value(self) -> str:
        """Return the current status."""
        return self._monitor.state

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional attributes."""
        attrs = {
            "power_entity": self._monitor.power_entity,
            "internal_state": self._monitor.internal_state,
        }
        if self._monitor.last_started:
            attrs["last_started"] = self._monitor.last_started.isoformat()
        if self._monitor.last_completed:
            attrs["last_completed"] = self._monitor.last_completed.isoformat()
        return attrs


class AppliancePowerSensor(ApplianceBaseSensor):
    """Sensor showing the current power consumption."""

    _attr_translation_key = "current_power"
    _attr_icon = "mdi:flash"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT

    def __init__(
        self, monitor: ApplianceMonitor, entry: ConfigEntry
    ) -> None:
        """Initialize the sensor."""
        super().__init__(monitor, entry)
        self._attr_unique_id = f"{entry.entry_id}_power"

    @property
    def native_value(self) -> float | None:
        """Return current power."""
        return self._monitor.current_power


class ApplianceCycleDurationSensor(ApplianceBaseSensor):
    """Sensor showing cycle duration: live elapsed time when running, last completed otherwise."""

    _attr_translation_key = "cycle_duration"
    _attr_icon = "mdi:timer-outline"
    _attr_native_unit_of_measurement = "min"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, monitor: ApplianceMonitor, entry: ConfigEntry
    ) -> None:
        """Initialize the sensor."""
        super().__init__(monitor, entry)
        self._attr_unique_id = f"{entry.entry_id}_cycle_duration"

    @property
    def native_value(self) -> float | None:
        """Return live elapsed time when running, or last completed duration."""
        if self._monitor.is_running and self._monitor.last_started is not None:
            elapsed = (dt_util.now() - self._monitor.last_started).total_seconds()
            return round(elapsed / 60, 1)
        if self._monitor.cycle_duration is not None:
            return round(self._monitor.cycle_duration / 60, 1)
        return None


class ApplianceCyclesTodaySensor(ApplianceBaseSensor):
    """Sensor showing the number of completed cycles today."""

    _attr_translation_key = "cycles_today"
    _attr_icon = "mdi:counter"
    _attr_state_class = SensorStateClass.TOTAL

    def __init__(
        self, monitor: ApplianceMonitor, entry: ConfigEntry
    ) -> None:
        """Initialize the sensor."""
        super().__init__(monitor, entry)
        self._attr_unique_id = f"{entry.entry_id}_cycles_today"

    @property
    def native_value(self) -> int:
        """Return cycles completed today."""
        return self._monitor.cycles_today


class ApplianceCycleEnergySensor(ApplianceBaseSensor):
    """Sensor showing the energy consumed in the last cycle."""

    _attr_translation_key = "cycle_energy"
    _attr_icon = "mdi:lightning-bolt"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, monitor: ApplianceMonitor, entry: ConfigEntry
    ) -> None:
        """Initialize the sensor."""
        super().__init__(monitor, entry)
        self._attr_unique_id = f"{entry.entry_id}_cycle_energy"

    @property
    def native_value(self) -> float | None:
        """Return energy consumed in last cycle."""
        return self._monitor.cycle_energy
