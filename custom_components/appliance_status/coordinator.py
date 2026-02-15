"""Appliance Monitor state machine coordinator."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
)
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ENERGY_ENTITY,
    CONF_POWER_ENTITY,
    DEFAULT_DEBOUNCE_TIME,
    DEFAULT_FINISH_DELAY,
    DEFAULT_RUNNING_THRESHOLD,
    DEFAULT_STANDBY_THRESHOLD,
    DEFAULT_START_DELAY,
    DOMAIN,
    EVENT_APPLIANCE_COMPLETED,
    STATE_COMPLETED,
    STATE_OFF,
    STATE_PENDING_COMPLETED,
    STATE_PENDING_RUNNING,
    STATE_RUNNING,
    STATE_STANDBY,
    CONF_APPLIANCE_NAME,
)

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1

# States that the sensor exposes (mapping internal -> external)
EXTERNAL_STATE_MAP = {
    STATE_OFF: STATE_OFF,
    STATE_STANDBY: STATE_STANDBY,
    STATE_PENDING_RUNNING: STATE_STANDBY,  # Show as standby while confirming
    STATE_RUNNING: STATE_RUNNING,
    STATE_PENDING_COMPLETED: STATE_RUNNING,  # Show as running while confirming
    STATE_COMPLETED: STATE_COMPLETED,
}


class ApplianceMonitor:
    """State machine that monitors appliance power consumption."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the appliance monitor."""
        self.hass = hass
        self.entry = entry

        self._power_entity: str = entry.data[CONF_POWER_ENTITY]
        self._energy_entity: str | None = entry.data.get(CONF_ENERGY_ENTITY)
        self._appliance_name: str = entry.data[CONF_APPLIANCE_NAME]

        # Internal state
        self._state: str = STATE_OFF
        self._current_power: float = 0.0
        self._last_state_change: datetime | None = None
        self._last_started: datetime | None = None
        self._last_completed: datetime | None = None
        self._cycle_duration: float | None = None
        self._cycles_today: int = 0
        self._cycles_today_date: str | None = None

        # Energy tracking
        self._energy_at_start: float | None = None
        self._cycle_energy: float | None = None

        # Configurable parameters (will be updated by number entities)
        self._standby_threshold: float = DEFAULT_STANDBY_THRESHOLD
        self._running_threshold: float = DEFAULT_RUNNING_THRESHOLD
        self._start_delay: int = DEFAULT_START_DELAY  # minutes
        self._finish_delay: int = DEFAULT_FINISH_DELAY  # minutes
        self._debounce_time: int = DEFAULT_DEBOUNCE_TIME  # seconds

        # Timers
        self._start_timer: CALLBACK_TYPE | None = None
        self._finish_timer: CALLBACK_TYPE | None = None
        self._debounce_timer: CALLBACK_TYPE | None = None

        # Listeners
        self._unsub_state_change: CALLBACK_TYPE | None = None
        self._update_callbacks: list[Callable[[], None]] = []

        # Persistent storage
        self._store = Store(
            hass,
            STORAGE_VERSION,
            f"{DOMAIN}.{entry.entry_id}",
        )

    @property
    def state(self) -> str:
        """Return the external state of the appliance."""
        return EXTERNAL_STATE_MAP.get(self._state, STATE_OFF)  # type: ignore[return-value]

    @property
    def internal_state(self) -> str:
        """Return the internal state (including pending states)."""
        return self._state

    @property
    def is_running(self) -> bool:
        """Return True if the appliance is running."""
        return self._state in (STATE_RUNNING, STATE_PENDING_COMPLETED)

    @property
    def current_power(self) -> float:
        """Return current power consumption."""
        return self._current_power

    @property
    def last_started(self) -> datetime | None:
        """Return when the last cycle started."""
        return self._last_started

    @property
    def last_completed(self) -> datetime | None:
        """Return when the last cycle completed."""
        return self._last_completed

    @property
    def cycle_duration(self) -> float | None:
        """Return duration of last cycle in seconds."""
        return self._cycle_duration

    @property
    def cycle_energy(self) -> float | None:
        """Return energy consumed in last cycle in kWh."""
        return self._cycle_energy

    @property
    def cycles_today(self) -> int:
        """Return number of completed cycles today."""
        today = dt_util.now().strftime("%Y-%m-%d")
        if self._cycles_today_date != today:
            self._cycles_today = 0
            self._cycles_today_date = today
        return self._cycles_today

    @property
    def appliance_name(self) -> str:
        """Return the appliance name."""
        return self._appliance_name

    @property
    def power_entity(self) -> str:
        """Return the power entity ID."""
        return self._power_entity

    # --- Parameter setters (used by number entities) ---

    def set_standby_threshold(self, value: float) -> None:
        """Set standby threshold."""
        self._standby_threshold = value
        _LOGGER.debug(
            "%s: Standby threshold set to %.1f W", self._appliance_name, value
        )

    def set_running_threshold(self, value: float) -> None:
        """Set running threshold."""
        self._running_threshold = value
        _LOGGER.debug(
            "%s: Running threshold set to %.1f W", self._appliance_name, value
        )

    def set_start_delay(self, value: int) -> None:
        """Set start delay in minutes."""
        self._start_delay = value
        _LOGGER.debug(
            "%s: Start delay set to %d min", self._appliance_name, value
        )

    def set_finish_delay(self, value: int) -> None:
        """Set finish delay in minutes."""
        self._finish_delay = value
        _LOGGER.debug(
            "%s: Finish delay set to %d min", self._appliance_name, value
        )

    def set_debounce_time(self, value: int) -> None:
        """Set debounce time in seconds."""
        self._debounce_time = value
        _LOGGER.debug(
            "%s: Debounce time set to %d s", self._appliance_name, value
        )

    # --- Callback registration ---

    def register_update_callback(self, callback_fn: Callable[[], None]) -> None:
        """Register a callback to be called when state changes."""
        self._update_callbacks.append(callback_fn)

    def unregister_update_callback(self, callback_fn: Callable[[], None]) -> None:
        """Unregister a previously registered callback."""
        if callback_fn in self._update_callbacks:
            self._update_callbacks.remove(callback_fn)

    def _notify_update(self) -> None:
        """Notify all registered callbacks about a state update."""
        for cb in self._update_callbacks:
            cb()

    # --- Start / Stop ---

    async def async_start(self) -> None:
        """Start monitoring the power sensor."""
        # Restore persisted state before starting
        await self._async_restore_state()

        self._unsub_state_change = async_track_state_change_event(
            self.hass, [self._power_entity], self._async_power_state_changed
        )

        # Read current state of the power sensor
        state = self.hass.states.get(self._power_entity)
        if state and state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            try:
                self._current_power = float(state.state)
                self._classify_power(self._current_power)
            except (ValueError, TypeError):
                _LOGGER.warning(
                    "%s: Could not parse initial power value: %s",
                    self._appliance_name,
                    state.state,
                )

        _LOGGER.info(
            "%s: Started monitoring %s (restored state: %s)",
            self._appliance_name,
            self._power_entity,
            self._state,
        )

    @callback
    def async_stop(self) -> None:
        """Stop monitoring."""
        if self._unsub_state_change:
            self._unsub_state_change()
            self._unsub_state_change = None
        self._cancel_start_timer()
        self._cancel_finish_timer()
        self._cancel_debounce_timer()
        _LOGGER.info("%s: Stopped monitoring", self._appliance_name)

    # --- Event handling ---

    @callback
    def _async_power_state_changed(self, event: Event) -> None:
        """Handle power sensor state changes."""
        new_state = event.data.get("new_state")
        if new_state is None or new_state.state in (
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
        ):
            return

        try:
            power = float(new_state.state)
        except (ValueError, TypeError):
            return

        self._current_power = power

        # Debounce: schedule classification after debounce period
        self._cancel_debounce_timer()
        self._debounce_timer = async_call_later(
            self.hass,
            self._debounce_time,
            self._debounce_callback,
        )

    @callback
    def _debounce_callback(self, _now: Any) -> None:
        """Called after debounce period with the latest power value."""
        self._debounce_timer = None
        self._classify_power(self._current_power)

    # --- State machine ---

    def _classify_power(self, power: float) -> None:
        """Classify power into raw state and run state machine transitions."""
        # Determine raw state from power value
        if power < self._standby_threshold:
            raw_state = STATE_OFF
        elif power < self._running_threshold:
            raw_state = STATE_STANDBY
        else:
            raw_state = STATE_RUNNING

        old_state = self._state
        self._transition(raw_state)

        if self._state != old_state:
            _LOGGER.debug(
                "%s: State changed %s -> %s (power=%.1f W)",
                self._appliance_name,
                old_state,
                self._state,
                power,
            )
            self._last_state_change = dt_util.now()
            self._notify_update()
            self.hass.async_create_task(self._async_save_state())

    def _transition(self, raw_state: str) -> None:
        """Execute state machine transition based on raw power state."""
        current = self._state

        if current == STATE_OFF:
            if raw_state == STATE_STANDBY:
                self._state = STATE_STANDBY
            elif raw_state == STATE_RUNNING:
                self._start_pending_running()

        elif current == STATE_STANDBY:
            if raw_state == STATE_OFF:
                self._state = STATE_OFF
            elif raw_state == STATE_RUNNING:
                self._start_pending_running()

        elif current == STATE_PENDING_RUNNING:
            if raw_state == STATE_OFF:
                self._cancel_start_timer()
                self._state = STATE_OFF
            elif raw_state == STATE_STANDBY:
                self._cancel_start_timer()
                self._state = STATE_STANDBY
            # If still running, timer continues

        elif current == STATE_RUNNING:
            if raw_state == STATE_OFF:
                self._start_pending_completed()
            elif raw_state == STATE_STANDBY:
                self._start_pending_completed()
            # If still running, stay in RUNNING

        elif current == STATE_PENDING_COMPLETED:
            if raw_state == STATE_RUNNING:
                # Power came back up - cancel completion, stay running
                self._cancel_finish_timer()
                self._state = STATE_RUNNING
            # If still standby/off, timer continues

        elif current == STATE_COMPLETED:
            if raw_state == STATE_OFF:
                self._state = STATE_OFF
            elif raw_state == STATE_STANDBY:
                self._state = STATE_STANDBY
            elif raw_state == STATE_RUNNING:
                self._start_pending_running()

    def _start_pending_running(self) -> None:
        """Start the pending_running state with start delay timer."""
        self._state = STATE_PENDING_RUNNING
        self._cancel_start_timer()

        delay = timedelta(minutes=self._start_delay)
        self._start_timer = async_call_later(
            self.hass,
            delay.total_seconds(),
            self._start_timer_callback,
        )
        _LOGGER.debug(
            "%s: Pending running, confirming in %d min",
            self._appliance_name,
            self._start_delay,
        )

    @callback
    def _start_timer_callback(self, _now: Any) -> None:
        """Timer expired - confirm running state."""
        self._start_timer = None
        if self._state == STATE_PENDING_RUNNING:
            self._state = STATE_RUNNING
            self._last_started = dt_util.now()
            self._energy_at_start = self._read_energy_value()
            _LOGGER.info("%s: Confirmed RUNNING", self._appliance_name)
            self._notify_update()
            self.hass.async_create_task(self._async_save_state())

    def _start_pending_completed(self) -> None:
        """Start the pending_completed state with finish delay timer."""
        self._state = STATE_PENDING_COMPLETED
        self._cancel_finish_timer()

        delay = timedelta(minutes=self._finish_delay)
        self._finish_timer = async_call_later(
            self.hass,
            delay.total_seconds(),
            self._finish_timer_callback,
        )
        _LOGGER.debug(
            "%s: Pending completed, confirming in %d min",
            self._appliance_name,
            self._finish_delay,
        )

    @callback
    def _finish_timer_callback(self, _now: Any) -> None:
        """Timer expired - confirm completion."""
        self._finish_timer = None
        if self._state == STATE_PENDING_COMPLETED:
            self._state = STATE_COMPLETED

            # Calculate cycle duration
            now = dt_util.now()
            self._last_completed = now
            if self._last_started is not None:
                delta = now - self._last_started
                self._cycle_duration = delta.total_seconds()

            # Calculate cycle energy
            energy_at_end = self._read_energy_value()
            if self._energy_at_start is not None and energy_at_end is not None:
                self._cycle_energy = round(
                    energy_at_end - self._energy_at_start, 3
                )
            self._energy_at_start = None

            # Increment daily counter
            today = now.strftime("%Y-%m-%d")
            if self._cycles_today_date != today:
                self._cycles_today = 0
                self._cycles_today_date = today
            self._cycles_today += 1

            duration_str = (
                str(timedelta(seconds=int(self._cycle_duration)))
                if self._cycle_duration is not None
                else "unknown"
            )
            energy_str = (
                f"{self._cycle_energy:.3f} kWh"
                if self._cycle_energy is not None
                else "N/A"
            )
            _LOGGER.info(
                "%s: COMPLETED (duration: %s, energy: %s)",
                self._appliance_name,
                duration_str,
                energy_str,
            )

            # Fire HA event
            self.hass.bus.async_fire(
                EVENT_APPLIANCE_COMPLETED,
                {
                    "entity_id": f"sensor.appliance_{self._make_slug()}_status",
                    "appliance_name": self._appliance_name,
                    "cycle_duration": self._cycle_duration,
                    "cycle_energy": self._cycle_energy,
                },
            )

            self._notify_update()
            self.hass.async_create_task(self._async_save_state())

    # --- Timer management ---

    def _cancel_start_timer(self) -> None:
        """Cancel pending start timer."""
        if self._start_timer:
            self._start_timer()
            self._start_timer = None

    def _cancel_finish_timer(self) -> None:
        """Cancel pending finish timer."""
        if self._finish_timer:
            self._finish_timer()
            self._finish_timer = None

    def _cancel_debounce_timer(self) -> None:
        """Cancel debounce timer."""
        if self._debounce_timer:
            self._debounce_timer()
            self._debounce_timer = None

    # --- Helpers ---

    def _make_slug(self) -> str:
        """Create a slug from the appliance name."""
        return self._appliance_name.lower().replace(" ", "_").replace("-", "_")

    def _read_energy_value(self) -> float | None:
        """Read the current value of the energy entity."""
        if self._energy_entity is None:
            return None
        state = self.hass.states.get(self._energy_entity)
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return None
        try:
            return float(state.state)
        except (ValueError, TypeError):
            return None

    # --- State persistence ---

    async def _async_save_state(self) -> None:
        """Save current state to persistent storage."""
        data = {
            "state": self._state,
            "last_started": (
                self._last_started.isoformat() if self._last_started else None
            ),
            "last_completed": (
                self._last_completed.isoformat()
                if self._last_completed
                else None
            ),
            "cycle_duration": self._cycle_duration,
            "cycles_today": self._cycles_today,
            "cycles_today_date": self._cycles_today_date,
            "cycle_energy": self._cycle_energy,
            "energy_at_start": self._energy_at_start,
        }
        await self._store.async_save(data)
        _LOGGER.debug("%s: State saved", self._appliance_name)

    async def _async_restore_state(self) -> None:
        """Restore state from persistent storage."""
        data = await self._store.async_load()
        if data is None:
            _LOGGER.debug("%s: No stored state to restore", self._appliance_name)
            return

        try:
            stored_state = data.get("state", STATE_OFF)
            # If appliance was mid-cycle (running/pending), restore as running
            # so it can detect the finish. If completed, restore as completed.
            if stored_state in (STATE_RUNNING, STATE_PENDING_RUNNING):
                self._state = STATE_RUNNING
            elif stored_state == STATE_PENDING_COMPLETED:
                self._state = STATE_RUNNING
            elif stored_state in (STATE_COMPLETED, STATE_STANDBY, STATE_OFF):
                self._state = stored_state
            else:
                self._state = STATE_OFF

            if data.get("last_started"):
                self._last_started = dt_util.parse_datetime(
                    data["last_started"]
                )
            if data.get("last_completed"):
                self._last_completed = dt_util.parse_datetime(
                    data["last_completed"]
                )

            self._cycle_duration = data.get("cycle_duration")
            self._cycles_today = data.get("cycles_today", 0)
            self._cycles_today_date = data.get("cycles_today_date")
            self._cycle_energy = data.get("cycle_energy")
            self._energy_at_start = data.get("energy_at_start")

            _LOGGER.info(
                "%s: Restored state: %s (cycles today: %d)",
                self._appliance_name,
                self._state,
                self._cycles_today,
            )
        except Exception:  # noqa: BLE001
            _LOGGER.warning(
                "%s: Failed to restore state, starting fresh",
                self._appliance_name,
            )
