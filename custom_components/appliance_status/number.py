"""Number platform for Appliance Status Monitor."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.device_registry import DeviceInfo

from .const import (
    CONF_APPLIANCE_NAME,
    DEFAULT_DEBOUNCE_TIME,
    DEFAULT_FINISH_DELAY,
    DEFAULT_RUNNING_THRESHOLD,
    DEFAULT_STANDBY_THRESHOLD,
    DEFAULT_START_DELAY,
    DOMAIN,
    MAX_DEBOUNCE_TIME,
    MAX_FINISH_DELAY,
    MAX_RUNNING_THRESHOLD,
    MAX_STANDBY_THRESHOLD,
    MAX_START_DELAY,
    MIN_DEBOUNCE_TIME,
    MIN_FINISH_DELAY,
    MIN_RUNNING_THRESHOLD,
    MIN_STANDBY_THRESHOLD,
    MIN_START_DELAY,
)
from .coordinator import ApplianceMonitor


@dataclass(frozen=True)
class ApplianceNumberDescription(NumberEntityDescription):
    """Describe an appliance number entity."""

    default_value: float = 0
    setter_fn: str = ""


NUMBER_DESCRIPTIONS: tuple[ApplianceNumberDescription, ...] = (
    ApplianceNumberDescription(
        key="standby_threshold",
        translation_key="standby_threshold",
        icon="mdi:flash-alert-outline",
        native_min_value=MIN_STANDBY_THRESHOLD,
        native_max_value=MAX_STANDBY_THRESHOLD,
        native_step=0.5,
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=NumberDeviceClass.POWER,
        mode=NumberMode.BOX,
        default_value=DEFAULT_STANDBY_THRESHOLD,
        setter_fn="set_standby_threshold",
    ),
    ApplianceNumberDescription(
        key="running_threshold",
        translation_key="running_threshold",
        icon="mdi:flash-alert",
        native_min_value=MIN_RUNNING_THRESHOLD,
        native_max_value=MAX_RUNNING_THRESHOLD,
        native_step=1.0,
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=NumberDeviceClass.POWER,
        mode=NumberMode.BOX,
        default_value=DEFAULT_RUNNING_THRESHOLD,
        setter_fn="set_running_threshold",
    ),
    ApplianceNumberDescription(
        key="start_delay",
        translation_key="start_delay",
        icon="mdi:timer-play",
        native_min_value=MIN_START_DELAY,
        native_max_value=MAX_START_DELAY,
        native_step=1,
        native_unit_of_measurement="min",
        mode=NumberMode.BOX,
        default_value=DEFAULT_START_DELAY,
        setter_fn="set_start_delay",
    ),
    ApplianceNumberDescription(
        key="finish_delay",
        translation_key="finish_delay",
        icon="mdi:timer-check",
        native_min_value=MIN_FINISH_DELAY,
        native_max_value=MAX_FINISH_DELAY,
        native_step=1,
        native_unit_of_measurement="min",
        mode=NumberMode.BOX,
        default_value=DEFAULT_FINISH_DELAY,
        setter_fn="set_finish_delay",
    ),
    ApplianceNumberDescription(
        key="debounce_time",
        translation_key="debounce_time",
        icon="mdi:timer-sand",
        native_min_value=MIN_DEBOUNCE_TIME,
        native_max_value=MAX_DEBOUNCE_TIME,
        native_step=5,
        native_unit_of_measurement="s",
        mode=NumberMode.BOX,
        default_value=DEFAULT_DEBOUNCE_TIME,
        setter_fn="set_debounce_time",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Appliance Status number entities."""
    monitor: ApplianceMonitor = entry.runtime_data

    entities = [
        ApplianceNumberEntity(monitor, entry, description)
        for description in NUMBER_DESCRIPTIONS
    ]
    async_add_entities(entities)


class ApplianceNumberEntity(NumberEntity):
    """Number entity for configuring appliance thresholds and delays."""

    _attr_has_entity_name = True
    entity_description: ApplianceNumberDescription

    def __init__(
        self,
        monitor: ApplianceMonitor,
        entry: ConfigEntry,
        description: ApplianceNumberDescription,
    ) -> None:
        """Initialize the number entity."""
        self._monitor = monitor
        self.entity_description = description

        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_native_value = description.default_value
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data[CONF_APPLIANCE_NAME],
            manufacturer="Appliance Status Monitor",
            model="Power Monitor",
        )

        # Restore from config entry options if available
        stored = entry.options.get(description.key)
        if stored is not None:
            self._attr_native_value = stored

    async def async_added_to_hass(self) -> None:
        """Set the initial value on the monitor when added to HA."""
        setter = getattr(self._monitor, self.entity_description.setter_fn)
        setter(self._attr_native_value)

    async def async_set_native_value(self, value: float) -> None:
        """Update the value and notify the monitor."""
        self._attr_native_value = value

        # Call the appropriate setter on the monitor
        setter = getattr(self._monitor, self.entity_description.setter_fn)
        setter(value)

        # Persist to config entry options
        new_options = dict(self.hass.config_entries.async_get_entry(
            self._monitor.entry.entry_id
        ).options)
        new_options[self.entity_description.key] = value
        self.hass.config_entries.async_update_entry(
            self._monitor.entry, options=new_options
        )

        self.async_write_ha_state()
