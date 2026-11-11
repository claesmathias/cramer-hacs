# Integration architecture and audit

[Index](README.md) · [Protocol reference](API_REFERENCE.md)

## Organization and data flow

**CONFIRMED IN CODE.** Domain `cramer_connect`, version 0.8.1. The manifest declares `config_flow` and `cloud_polling`, with no additional requirements or integration dependencies. aiohttp and voluptuous are supplied by Home Assistant. Development requirements are pytest, pytest-asyncio and aiohttp. CI runs Python 3.13, HACS validation, Hassfest and unit tests with the live test file explicitly excluded.

| Component | Responsibility |
|---|---|
| `config_flow.py` | Login, unique account ID using lowercase email, reauthentication and PIN options |
| `__init__.py` | Shared HA aiohttp session and TLS context, initial login/refresh, platform forwarding and unloading |
| `api.py` | CramerAuth/CramerDevice/ScheduleTimer dataclasses, Fleet/Xlink paths, datapoint parsing, binary command builders and minimal MQTT client |
| `const.py` | Hosts, product codes, states, errors and command formats |
| `coordinator.py` | 30-second polling, reauthentication, bounded auth retry and 120-second optimistic schedule cache |
| `entity.py` | Shared control methods, PIN handling, command sending, refresh and schedule services |
| `sensor.py`, `binary_sensor.py` | State/reason, battery, next start, last report, statistics, errors, versions, signal strength, GPS, online and charging |
| `lawn_mower.py`, `button.py` | Start/pause/dock and timed/indefinite/end-of-day parking; start/pause buttons disabled by default |
| `calendar.py` | Weekly schedule expansion in the HA time zone; two windows per day |
| `device_tracker.py` | Robot GPS position |
| `update.py` | Installed/offered firmware versions; read-only, no installation action |
| `diagnostics.py` | Identity/location redaction and decoding nested JSON datapoint values |
| `services.yaml`, strings, translations, icons, brand | Schemas and presentation; English translation provided |

Flow: config entry → authentication → coordinator → device list plus concurrent per-device enrichment → dictionary keyed by device ID → entities. A service builds a hexadecimal command → coordinator → MQTT/TLS → PUBACK → HTTP refresh. Tokens remain in memory; email/password are stored in config entry data and the PIN in options. There is no separate custom encrypted credential store. Existing conventions include `hass.data[DOMAIN]`, CoordinatorEntity and shared asynchronous client methods.

## Existing capabilities

RLM1/RLM2 selection uses productCode. If it is missing, `is_mower` accepts a device with a populated state. Controls explicitly exclude RLM2. Services already include `park`, `set_schedule`, `start_nonstop_mowing`, `cancel_nonstop_mowing` and `set_clock`. A native lawn_mower entity already exists; it should not be implemented again.

## Findings and limitations

1. `_is_fleet_user` treats exceptions and any non-200 HTTP response as a consumer account. A Fleet outage can redirect login and produce misleading errors.
2. `_get_xlink_device_state` returns `{}` for all non-200 responses, including 401; `_enrich_devices` absorbs exceptions. A refresh can appear successful without telemetry or triggering authentication recovery. List and datapoint failures need separate handling.
3. The coordinator repeats full login at expiry instead of consuming stored refresh tokens. It ignores Fleet expiration and Xlink's returned `expire_in`, using min(GUC, 7200) when an Xlink token exists, or GUC expiry alone otherwise. There is no reauthentication lock between commands and polling.
4. `send_command` logs the complete command payload at debug level. Start commands can contain the PIN. HTTP error bodies are also copied into logs/exceptions and may contain sensitive data.
5. `CramerMowerEntity.available` checks online status and MQTT credentials but omits `coordinator.last_update_success`. Other platforms implement their own availability. Calendar intentionally keeps a known schedule while the robot is offline. An experimental native-entity availability override was reviewed separately and withdrawn from the native-controls proposal to keep that behavioral change independent.
6. `supports_remote_control` accepts any product code except RLM2. An unknown product with state data might receive controls. Lack of evidence for RLM2 cloud control does not prove universal impossibility.
7. The minimal MQTT implementation opens CONNECT/PUBLISH QoS1/DISCONNECT per command. PUBACK confirms broker receipt, not physical execution. It does not consume semantic results or `$6`/`$8` events. There is no persistent connection or bound on concurrent enrichment requests.
8. `validate_day_timers` checks only active timers. Negative/disabled values and binary ranges need stronger validation. `_le16` masks values. HA schemas reduce some exposure but do not cover all direct client inputs.
9. Diagnostic redaction relies on known key names. `raw` may contain new sensitive fields or opaque JSON strings. Nested tokens and authorizations need tests; universal anonymization is not established.
10. Entities are created during setup; discovery of newly added devices without reload needs verification. Fleet `get_device_status` exists in the client but ordinary enrichment queries Xlink.

These are static observations and reasoned risks, not reproductions against Cramer servers or a real HA instance.

## Tests and verification history

The initial audit found 227 test functions in test_api.py, test_controls.py and test_sensors.py; that is neither the parametrized case count nor a coverage percentage. They cover parsing, auth branches/errors, command builders, MQTT with a local simulated broker, entities, schedules, clock, firmware and diagnostics. conftest.py injects HA stubs: useful for logic but insufficient to verify real lifecycle/API compatibility. Coverage was not measured; real config flow/setup/unload tests and complete session/failure scenarios remain useful additions.

Safe command: `python3 -m pytest -q --ignore=tests/test_login_live.py`. Initially pytest was unavailable and no tests ran. A later native-controls session installed the already-declared development requirements in a temporary venv and passed 292 cases on Python 3.14, including an experimental availability test. That result is historical, not a test run of this documentation-only branch. CI declares Python 3.13.

Never omit the live-file exclusion: that file can automatically read credentials from the environment or .env. The native-controls contribution records its own current test results separately.

## Source locators

All paths below are under `custom_components/cramer_connect/` in the baseline checkout:

| File | Symbol and line |
|---|---|
| api.py | CramerAuth:266; authenticate:364; _is_fleet_user:443; _get_xlink_device_state:676; send_command:873; _mqtt_publish:1020 |
| coordinator.py | _async_update_data:61; force_reauth:108; _ensure_auth:120 |
| config_flow.py | async_step_user:52; async_step_reauth_confirm:85 |
| diagnostics.py | device_diagnostics:49 |

## Consistency check against the functional integration

The production files under custom_components/ are identical in main (baseline commit 3414dbf), docs/cramer-api-research and the current native-controls test branch at the time of this check. Existing START_MOWING/PAUSE/DOCK methods, shared button commands, MQTT transport and schedule services agree with this documentation. The roadmap lists proposed improvements, not already-applied fixes; API entries explicitly distinguish implemented methods from Android-only declarations.

Documentation clarifications from this check:

- Automatic session renewal repeats login; stored refresh tokens are not consumed by the coordinator. The main README now uses session renewal rather than implying a refresh-token grant.
- The min(GUC,7200) deadline applies only when an Xlink token exists; without it CramerAuth uses GUC expiry alone.
- HACS excludes RLM2 remote controls. BLE is confirmed for the examined Android flows, but universal absence of cloud controls is not proven.
- The withdrawn availability override is not present in current production code. Historical test counts refer to the stated branch/session, not documentation-only changes.

The contributor reports working control buttons on a Cramer RM1500: start, pause, return-to-base/indefinite park and end-of-day park. This is user-reported physical validation of those controls, not an automated device test or verification of all schedules, firmware operations, account types or native frontend behavior. The main README records the same scope.
