# Cramer Connect for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![GitHub release](https://img.shields.io/github/v/release/claesmathias/cramer-hacs)](https://github.com/claesmathias/cramer-hacs/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A Home Assistant custom integration for **Cramer Connect** robotic lawn mowers (RLM1 / RLM2), using the same cloud API as the official Cramer Connect mobile app.

## Features

- **Lawn mower** entity — start, pause and dock from the HA UI (RLM1)
- **Control buttons** — start, pause, park until further notice, park for the rest of the day (RLM1)
- `cramer_connect.park` service to park for a chosen number of minutes
- Mower **state** sensor (`mowing`, `charging`, `parked`, ...) with the parked reason
- **Battery**, **next start**, **last error**, statistics, GPS position, software version
- Optional **PIN code** for mowers that need it to accept a start command
- Automatic **session renewal** — signs in again when tokens expire, without asking for your credentials again
- Polling every **30 seconds**
- Works with all Cramer fleet accounts (same login as the Cramer Connect app)

## Supported devices

| Model | Supported |
|---|---|
| Cramer RLM1 (robotic lawn mower gen 1) | ✅ |
| Cramer RLM2 (robotic lawn mower gen 2) | ✅ |

### Tested hardware

| Model | Tested by | Result |
|---|---|---|
| Cramer RM1500 | [@davidpicon7](https://github.com/davidpicon7) | Start mowing, pause, park until further notice and park for the rest of the day work |
| Cramer RM1000 | maintainer | Login, live data, schedule and command-channel login work; commands not yet tried |

This covers the tested robots only, not every model or firmware version. The lawn mower entity sends the same commands as the buttons. Tested another model? Please [open an issue](https://github.com/claesmathias/cramer-hacs/issues) with the results.

## Installation

### Via HACS (recommended)

1. Open HACS in Home Assistant.
2. Go to **Integrations** → click the three-dot menu → **Custom repositories**.
3. Add `https://github.com/claesmathias/cramer-hacs` with category **Integration**.
4. Search for **Cramer Connect** and install it.
5. Restart Home Assistant.

### Manual

1. Copy the `custom_components/cramer_connect` folder into your HA `config/custom_components/` directory.
2. Restart Home Assistant.

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for **Cramer Connect**.
3. Enter your **Cramer Connect app email and password**.

The integration will automatically discover all mowers linked to your account.

## Entities

For each mower the following entities are created:

| Entity | Type | Description |
|---|---|---|
| `lawn_mower.<name>` | Lawn mower | Start / pause / dock (RLM1 only) |
| `button.<name>_park_until_further_notice` | Button | Return to the charging station and stay there |
| `button.<name>_park_for_the_rest_of_the_day` | Button | Return to the charging station until midnight |
| `button.<name>_start_mowing`, `button.<name>_pause` | Button | Same as the lawn mower entity; **disabled by default** |
| `sensor.<name>_state` | Sensor | State as in the app, e.g. *Mowing*, *Parked by schedule*, *Parked by rain guard* |
| `sensor.<name>_status` | Sensor | One-line status like the app, e.g. *Parked by user until further notice* |
| `sensor.<name>_battery` | Sensor | Battery level (%) |
| `binary_sensor.<name>_charging` | Binary sensor | On while charging |
| `sensor.<name>_next_start` | Sensor | Next scheduled start |
| `sensor.<name>_last_seen` | Sensor | When the mower last reported in |
| `sensor.<name>_total_mowing_time` / `_running_time` / `_charging_time` | Sensor | Lifetime statistics (hours) |
| `sensor.<name>_total_mowing_distance` | Sensor | Lifetime distance (km) |
| `device_tracker.<name>` | Device tracker | Mower position on the map |
| `calendar.<name>_mowing_schedule` | Calendar | Weekly mowing windows from the mower's schedule |
| `button.<name>_set_clock` | Button | Set the mower clock to Home Assistant's time (configuration) |
| `update.<name>_firmware` | Update | Installed vs. offered firmware (diagnostic) |

Diagnostic entities: last error, error count, software version, WiFi signal, mobile signal, online. Latitude and longitude sensors exist but are disabled by default; the device tracker already shows the position on the map.

A diagnostics file (tokens, serial numbers and location removed) can be downloaded from the integration's device page for bug reports.

### Schedule

The mower's weekly schedule (two timers per day, as in the app) shows up in the Home Assistant calendar. Change it with these actions, which target the lawn mower entity:

| Action | What it does |
|---|---|
| `cramer_connect.set_schedule` | Set timer 1 and/or 2 for the selected weekdays; other days keep their timers. Leave a timer's times empty to turn it off. `00:00` as an end time means midnight. |
| `cramer_connect.start_nonstop_mowing` | Mow continuously and ignore the schedule for 1–24 days |
| `cramer_connect.cancel_nonstop_mowing` | Follow the schedule again |
| `cramer_connect.set_clock` | Set the mower clock to Home Assistant's time and time zone |

```yaml
action: cramer_connect.set_schedule
target:
  entity_id: lawn_mower.my_mower
data:
  days: [monday, wednesday, friday]
  timer_1_start: "09:00"
  timer_1_end: "12:00"
  timer_2_start: "14:00"
  timer_2_end: "17:30"
```

The same rules as in the app apply: a timer has to end after it starts, it can't run past midnight, and the two timers of a day can't overlap.

### Remote control

Commands are sent the same way the app sends them: MQTT messages to `mqtt.globetools.systems:1884` (TLS). This works for **RLM1** mowers. **RLM2** mowers are controlled over Bluetooth only, so no control entities are created for them.

If the mower's security setting requires a PIN code to start, set it under **Settings → Devices & Services → Cramer Connect → Configure**.

```yaml
service: cramer_connect.park
target:
  entity_id: lawn_mower.my_mower
data:
  duration: 120  # minutes; leave out to park until further notice
```

### Mower states

| State | Description |
|---|---|
| `mowing` | Actively mowing |
| `mowing_secondary_area` | Mowing the secondary zone |
| `charging` | Charging at the charging station |
| `leaving_charging_station` | Leaving the charging station |
| `searching_charging_station` | Returning to the charging station |
| `parked_by_schedule` | Parked until the next scheduled start |
| `parked_by_user` | Parked by the user |
| `parked_by_rain_guard` / `parked_by_frost_guard` | Parked by a weather guard |
| `parked_max_day_cutting` | Maximum daily mowing time reached |
| `energy_saving_mode` | Energy saving mode |
| `parked` | Parked, reason unknown |
| `paused` | Paused by the user |
| `stop_button_pressed` | Stopped via the stop button |
| `starting_up` | Booting up |
| `error` | Non-fatal error |
| `fatal_error` | Fatal error |
| `recovery_state` | Recovering from an error |
| `alarm_state` | Alarm triggered |

The `raw_state` attribute on the state sensor contains the original numeric code reported by the mower.

## Example automation

```yaml
automation:
  - alias: "Notify when mower has an error"
    trigger:
      - platform: state
        entity_id: lawn_mower.my_mower
        to: "error"
    action:
      - service: notify.mobile_app_phone
        data:
          message: "Cramer mower needs attention!"
```

## Troubleshooting

**Integration shows unavailable after a while**
The mower reports offline when it loses the cloud connection (e.g. out of WiFi range). This is expected — the state will recover once the mower reconnects.

**Authentication error on setup**
Make sure you are using the credentials from the **Cramer Connect** app, not a GreenWorks or Powerworks account.

**No mowers found**
The integration only lists devices with product code `RLM1` or `RLM2`. Other Cramer devices (batteries, vehicles) are not shown yet.

## Contributing

Pull requests are welcome. Please open an issue first to discuss larger changes.

## Disclaimer

This integration is not affiliated with or endorsed by Cramer Tools or Globe Tools Group. It was built by reverse-engineering the Cramer Connect Android app for personal use. Use at your own risk.

## License

MIT — see [LICENSE](LICENSE).
