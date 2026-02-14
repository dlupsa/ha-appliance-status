# 🔌 Appliance Status Monitor

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Home Assistant custom integration that monitors appliance power consumption and automatically detects operational cycles. Know when your washing machine, dryer, or dishwasher has finished — no cloud services required.

![Icon](custom_components/appliance_status/icon.png)

## Features

- 🔍 **Automatic cycle detection** — monitors power consumption to determine if an appliance is off, on standby, running, or has completed a cycle
- ⚡ **Configurable thresholds** — adjust power thresholds via slider entities directly in the HA dashboard
- ⏱️ **Anti-false-positive logic** — debounce mechanism and confirmation delays prevent false state changes
- 📊 **Rich attributes** — track cycle duration, cycle count today, power consumption
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
4. Select the power consumption sensor entity

## Entities

Each configured appliance creates the following entities:

### Status Sensor
`sensor.appliance_<name>_status` — current state of the appliance:
- **Off** — power below standby threshold
- **Standby** — power above standby threshold but below running threshold
- **Running** — actively operating (confirmed after start delay)
- **Completed** — cycle has finished

**Attributes:**
- `current_power` — current power consumption (W)
- `last_started` — timestamp of last cycle start
- `last_completed` — timestamp of last cycle completion
- `cycle_duration` — duration of last cycle (seconds)
- `cycles_today` — number of completed cycles today

### Binary Sensor
`binary_sensor.appliance_<name>_running` — simple on/off for whether the appliance is running.

### Number Entities (Configuration Sliders)

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
          message: "Pralni stroj je končal s pranjem"
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

## License

MIT License — see [LICENSE](LICENSE) for details.
