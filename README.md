# Cramer Connect for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![GitHub release](https://img.shields.io/github/v/release/claesmathias/cramer-hacs)](https://github.com/claesmathias/cramer-hacs/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A Home Assistant custom integration for **Cramer Connect** robotic lawn mowers (RLM1 / RLM2), using the same cloud API as the official Cramer Connect mobile app.

## Features

- Mower **state** sensor — `mowing`, `charging`, `parked`, `paused`, `error`, and more
- **Battery level** sensor (%)
- Automatic **token refresh** — stays connected without re-entering credentials
- Polling every **30 seconds**
- Works with all Cramer fleet accounts (same login as the Cramer Connect app)

## Supported devices

| Model | Supported |
|---|---|
| Cramer RLM1 (robotic lawn mower gen 1) | ✅ |
| Cramer RLM2 (robotic lawn mower gen 2) | ✅ |

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
| `sensor.<name>_state` | Sensor | Current mower state |
| `sensor.<name>_battery` | Sensor | Battery level (%) |

### Mower states

| State | Description |
|---|---|
| `mowing` | Actively mowing |
| `mowing_secondary_area` | Mowing the secondary zone |
| `charging` | Charging at the charging station |
| `leaving_charging_station` | Leaving the charging station |
| `searching_charging_station` | Returning to the charging station |
| `parked` | Parked (various reasons — see `raw_state` attribute) |
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
        entity_id: sensor.my_mower_state
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
