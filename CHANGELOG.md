# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.8.2] - 2026-11-13

Robustness fixes found during a code review by
[@davidpicon7](https://github.com/davidpicon7) in #4.

### Fixed
- A network error, timeout, HTTP 429 or 5xx while checking the account type
  no longer treats a fleet account as a consumer account. Before, this failed
  the login and asked for re-authentication although the password was fine;
  now setup is retried later instead.
- An expired token on the live-data call (HTTP 401) now triggers one
  re-login. Before, it was ignored and sensors showed stale data.
- The xlink token lifetime is taken from the login response instead of
  always assuming 2 hours.
- Simultaneous re-logins (for example a button press during a refresh) are
  merged into one.
- Every schedule timer value is range-checked before it is sent, including
  timers that are turned off.
- The diagnostics download redacts more token-like keys.

### Documentation
- Tested hardware: the Cramer RM1500 controls were confirmed by
  @davidpicon7.

## [0.8.1] - 2026-11-08

First stable release, ready for HACS.

### Added
- GitHub Actions workflow running HACS validation, hassfest and the unit tests.

### Fixed
- `manifest.json` keys sorted as hassfest requires.
- `icons.json` no longer defines a state icon for the free-text Last error
  sensor, which hassfest rejects.

## [0.8.0] - 2026-11-08

Schedule support, matching the app's Schedule screen.

### Added
- **Mowing schedule** calendar entity built from the weekly timers (dp 125).
  It stays available while the mower is offline.
- `cramer_connect.set_schedule` action: set the two timers of one or more
  weekdays and keep the other days as they are. It applies the app's rules:
  end after start, no running past midnight, no overlapping timers.
- `cramer_connect.start_nonstop_mowing` (1–24 days) and
  `cramer_connect.cancel_nonstop_mowing` actions.
- `cramer_connect.set_clock` action and a **Set clock** button that set the
  mower clock to Home Assistant's time and time zone.
- The Status sensor shows "Mowing nonstop until …", and the lawn mower and
  calendar entities have a `nonstop_mowing` attribute.

### Notes
- After a schedule change, the calendar shows the new schedule right away and
  keeps it for up to 2 minutes until the cloud reports the update.

## [0.7.0] - 2026-11-08

UI overhaul, modelled on the app's home, statistics and software screens.

### Added
- **Status** sensor with the app's one-line status, e.g. "Parked by user until
  further notice", "Charging until 14:00", "Fatal error: Mower is stuck.".
- **Last seen** timestamp sensor (when the mower last reported in).
- **Charging** binary sensor.
- **WiFi signal** and **Mobile signal** diagnostic sensors.
- **Firmware** `update` entity comparing the installed version with the
  firmware offered to the mower (dp 119).
- Diagnostics download with tokens, serial numbers and location redacted.
- `icons.json` with state-dependent icons.

### Changed
- The state sensor is now an enum sensor with translated values ("Stop button
  pressed" instead of `stop_button_pressed`). `parked` is split into the
  app's reasons: `parked_by_schedule`, `parked_by_user`, `parked_by_rain_guard`,
  `parked_by_frost_guard`, `parked_max_day_cutting`, `energy_saving_mode`,
  and `charging`. **Automations that check for `parked` need updating.**
- All entity names come from translations.
- Last error, error count, software version, online and signal sensors are
  now diagnostic entities. Latitude and longitude are disabled by default.
- The Start mowing and Pause buttons are disabled by default, because the
  lawn mower entity covers them.
- Mowing, running and charging time and distance display as whole numbers.
- The software version now comes from dp 117 (falls back to dp 246).

### Removed
- "Update available" binary sensor. Its `sw_update` flag stayed on even when
  the installed firmware matched the offered one. Replaced by the `update`
  entity and removed from the entity registry automatically.

## [0.6.0] - 2026-11-08

Brought in line with Cramer Connect app 4.5.0.

### Added
- Remote control over MQTT, the same channel the app uses (topic `$7/<device id>`
  on `mqtt.globetools.systems:1884`). Replaces the SignalR guess, which never
  worked. RLM1 only; RLM2 is Bluetooth-only.
- `lawn_mower` entity (start mowing / pause / dock) and a `cramer_connect.park`
  service with an optional duration in minutes.
- Buttons: Pause, Park until further notice, Park for the rest of the day.
- PIN code option for mowers whose security level (dp 8) requires it.
- "Last error" sensor (dp 33) with the app's error texts.
- `reason` attribute on the state sensor (parked by schedule / user / rain
  guard / frost guard, charging, energy saving mode, ...).
- Fleet accounts now fetch xlink credentials (`/api/account/XlinkToken`), so
  they get live datapoints and remote control too.
- Re-authentication flow when the stored password stops working.

### Fixed
- Expired or revoked tokens now trigger one silent re-login instead of
  immediately asking for re-authentication.
- Re-login happens before the 2-hour xlink token expires, even when the GUC
  token lives longer.
- `next_start` of 0 or -1 ("until further notice") no longer shows as a date.
- xlink requests send the GUC bearer token, as the app does.

### Changed
- The "Return to dock" button is now "Park until further notice" and
  "Park until next schedule" is now "Park for the rest of the day". These
  match the options the app offers. Unique IDs are unchanged.

## [0.1.2] - 2026-05-25

### Fixed
- Removed `aiohttp` from `manifest.json` requirements — it is bundled with
  Home Assistant and listing it caused a dependency conflict that crashed HA
  on startup (exit code 100)
- Removed unused `FLEET_AUTH_URL` import that could trigger a load-time error

## [0.1.1] - 2026-05-25

### Fixed
- Auth flow now matches the actual Cramer Connect app: fleet login followed by
  GUC token exchange via the fleet API (`/api/account/GucToken`), instead of a
  direct password grant to the GUC server
- Added required request headers (`ApplicationKey`, `Brand`, `App-Name`) that
  the server expects on every call

## [0.1.0] - 2026-05-25

### Added
- Initial release
- Mower state sensor (13 states: mowing, charging, parked, error, etc.)
- Battery level sensor
- Automatic GUC token refresh with fallback re-authentication
- Config flow UI (email + password)
- Support for RLM1 and RLM2 robotic lawn mowers
- 30-second polling via `DataUpdateCoordinator`
