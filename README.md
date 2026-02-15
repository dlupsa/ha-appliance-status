# 🔌 Appliance Status Monitor

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/dlupsa/ha-appliance-status)](https://github.com/dlupsa/ha-appliance-status/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Home Assistant custom integration that monitors appliance power consumption and automatically detects operational cycles. Know when your washing machine, dryer, or dishwasher has finished — no cloud services required.

![Icon](custom_components/appliance_status/icon.png)

## Features

- 🔍 **Automatic cycle detection** — monitors power consumption to determine if an appliance is off, on standby, running, or has completed a cycle
- ⚡ **Configurable thresholds** — adjust power thresholds via number input entities directly in the HA dashboard
- ⏱️ **Anti-false-positive logic** — debounce mechanism and confirmation delays prevent false state changes
- 📊 **Dedicated sensors** — current power, cycle duration, cycles today, and energy per cycle
- 🔋 **Energy tracking** — optional energy entity (kWh) to track consumption per cycle
- 🔔 **Event-based notifications** — fires `appliance_status_completed` event for use in HA automations
- 🌍 **Multi-language** — English and Slovenian translations included

## Installation

### HACS (Recommended)

1. Open HACS in your Home Assistant instance
2. Click the three dots menu → **Custom repositories**
3. Add this repository URL and select **Integration** as the category
4. Click **Install**
5. Restart Home Assistant

### Manual

1. Copy the `custom_components/appliance_status` folder to your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant

## Setup

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Appliance Status Monitor**
3. Enter a name for your appliance (e.g., "Pralni stroj")
4. Select the **power consumption sensor** entity (W)
5. Optionally select an **energy sensor** entity (kWh) to track energy per cycle

## Entities

Each configured appliance creates the following entities:

### Sensors

| Entity | Description |
|---|---|
| **Status** | Current state: Off, Standby, Running, Completed |
| **Current power** | Real-time power consumption (W) |
| **Cycle duration** | Duration of last completed cycle (min) |
| **Cycles today** | Number of completed cycles today |
| **Cycle energy** | Energy consumed in last cycle (kWh) — requires energy entity |

The Status sensor also includes additional attributes:
- `internal_state` — raw state machine state (including pending states)
- `last_started` — timestamp of last cycle start
- `last_completed` — timestamp of last cycle completion

### Binary Sensor
`binary_sensor.appliance_<name>_running` — simple on/off for whether the appliance is running.

### Number Entities (Configuration)

All number entities use text box input for precise value entry.

| Entity | Default | Unit | Description |
|---|---|---|---|
| Standby threshold | 2 | W | Power above this = standby |
| Running threshold | 8 | W | Power above this = running |
| Start confirmation delay | 5 | min | Time before confirming "running" |
| Finish confirmation delay | 2 | min | Time before confirming "completed" |
| Debounce time | 20 | s | Minimum time between state checks |

## State Machine

```
         ┌──────┐
         │  OFF │
         └──┬───┘
            │ power ≥ standby
            ▼
       ┌─────────┐
       │ STANDBY │◄──────────────────────┐
       └──┬──────┘                       │
          │ power ≥ running              │
          ▼                              │
  ┌───────────────┐                      │
  │PENDING RUNNING│                      │
  └──┬────────────┘                      │
     │ after start_delay                 │
     ▼                                   │
  ┌─────────┐                            │
  │ RUNNING │                            │
  └──┬──────┘                            │
     │ power drops                       │
     ▼                                   │
┌──────────────────┐                     │
│PENDING COMPLETED │                     │
└──┬───────────────┘                     │
   │ after finish_delay                  │
   ▼                                     │
┌───────────┐                            │
│ COMPLETED ├────────────────────────────┘
└───────────┘
```

## Automation Example

Use the `appliance_status_completed` event in your automations:

```yaml
automation:
  - alias: "Washing Machine Finished"
    trigger:
      - platform: event
        event_type: appliance_status_completed
        event_data:
          appliance_name: "Pralni stroj"
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "Pralni stroj je končal"
          message: >
            Pranje končano!
            Trajanje: {{ trigger.event.data.cycle_duration | int // 60 }} min
            Poraba: {{ trigger.event.data.cycle_energy }} kWh
```

Or trigger on the sensor state:

```yaml
automation:
  - alias: "Dryer Finished"
    trigger:
      - platform: state
        entity_id: sensor.appliance_susilec_status
        to: "completed"
    action:
      - service: tts.google_say
        data:
          entity_id: media_player.google_home
          message: "Sušilni stroj je zaključil s sušenjem."
```

## Changelog

### v1.2.0
- ✨ Optional energy entity (kWh) for tracking energy per cycle
- ✨ New dedicated sensors: Current Power, Cycle Duration, Cycles Today, Cycle Energy
- 🔧 Number inputs changed from sliders to text boxes for precise value entry
- 🌍 Updated translations (EN, SL)
- 🔖 HACS version tracking via GitHub releases

### v1.0.0
- 🎉 Initial release
- Power-based state machine with configurable thresholds
- Binary sensor, number entities, event support
- English and Slovenian translations

## License

MIT License — see [LICENSE](LICENSE) for details.
