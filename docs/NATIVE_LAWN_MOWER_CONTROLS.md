# Existing native lawn mower controls

[Index](README.md) · [Architecture](ARCHITECTURE.md) · [API reference](API_REFERENCE.md)

## Review outcome

Version 0.8.1 already derives from LawnMowerEntity, advertises START_MOWING | PAUSE | DOCK (bitmask 7), and implements the three official async methods. Keep those implementations, one entity per robot and unique_id `<device_id>_lawn_mower`. The disabled-by-default start/pause buttons do not need enabling for native actions.

| Official HA action | Method | Shared button logic |
|---|---|---|
| lawn_mower.start_mowing | async_start_mowing | async_start, same PIN and start/resume payload |
| lawn_mower.pause | async_pause | async_stop, including the secondary-area variant |
| lawn_mower.dock | async_dock | async_park(None), indefinite parking |

Controls use the existing remotely_controllable filter, explicitly excluding RLM2. Availability currently requires the device to be present/online and MQTT credentials. Unknown productCode handling remains unchanged. A coordinator.last_update_success availability override was prototyped separately and withdrawn from this proposal: it is an independent behavior change, not required to enable native commands. This branch contains documentation only; control regression tests belong in their own branch.

## DOCK semantics

DOCK means **Park until further notice**: return to base and stay parked indefinitely, duration value 0xfffe. This is confirmed by the shared async_park(None) calls in CramerStopButton.async_press and CramerLawnMower.async_dock, build_park_command, and the Android path in API_REFERENCE.

**Park for the rest of the day** remains a separate button and calculates minutes until day end. cramer_connect.park also supports a duration. Neither is synonymous with indefinite DOCK. Start/pause buttons are alternate entry points into the same code, not additional native capabilities.

The user has manually confirmed their start/pause/park buttons work. Native service dispatch and card presentation still require their manual verification. No physical orders were sent during this work.

## Acknowledgement, errors and state

The entity awaits coordinator.async_send_command before requesting async_request_refresh. It does not assign MOWING/PAUSED/RETURNING when a command is clicked; activity follows telemetry. Stale telemetry retains the old state until polling (30 seconds) catches up. A robot rejection without a state change is not currently interpreted semantically.

The existing transport completes after MQTT QoS1 PUBACK: broker receipt, not physical execution. Completion of an HA action therefore does not guarantee robot execution. Device-level confirmation requires reconstructing/correlating MQTT responses. Do not add an artificial wait that interprets old state as confirmation or invent a new protocol.

Client errors become HomeAssistantError; the entity does not refresh or resend after send failure. The coordinator reauthenticates/retries once only after explicit MQTT login refusal (CONNACK before PUBLISH). Timeouts/ambiguous results do not trigger automatic resend. Two requested actions remain two commands; no click deduplication or MQTT policy change is proposed.

## Activity mapping

| Cramer state | Existing HA activity | Qualification |
|---|---|---|
| 0: starting up | DOCKED | Ambiguous; preserve current behavior |
| 1: physical stop | PAUSED | Preserve |
| 2: parked | DOCKED | Physical location not independently verified |
| 3: paused | PAUSED | Preserve |
| 4: mowing; 12: secondary area | MOWING | Based on reported state |
| 5: leaving base | MOWING | Existing behavior; not proof blade is active |
| 6: searching for base | RETURNING | Existing MOWING fallback if HA lacks RETURNING |
| 7: charging | DOCKED | Preserve |
| 8/9/10/11: error/fatal/recovery/alarm | ERROR | Preserve |
| Missing/unrecognized | None (unknown) | Do not invent activity |

HA IDLE means stopped but neither docked nor paused. No unambiguous Cramer code was identified for it. Ambiguous existing mappings are documented rather than reinterpreted here.

## Manual checks in Home Assistant

These steps are for the user to run when ready to move the robot. No HA deployment, configuration change or restart was performed by the agent.

1. In **Developer tools → States**, inspect the existing lawn_mower.cortacesped_222030193. Check availability and supported_features=7. Compare native activity with the detailed state sensor.
2. In **Developer tools → Actions** (Services in older versions), run the actions individually. Change action to lawn_mower.pause or lawn_mower.dock for the other checks:

   ```yaml
   action: lawn_mower.start_mowing
   target:
     entity_id: lawn_mower.cortacesped_222030193
   ```

3. Check actual movement and later telemetry. Pause, then dock; observe returning and docked as reported. Wait for polling rather than immediately repeating an order when telemetry is delayed.
4. Verify DOCK leaves the robot parked indefinitely. Compare end-of-day parking in a separate test, not by sending both orders together. Keep the existing PIN option if required.
5. Use this tile with the existing entity. start_pause combines start/pause according to activity; it is not a new service:

   ```yaml
   type: tile
   entity: lawn_mower.cortacesped_222030193
   name: Cramer
   features:
     - type: lawn-mower-commands
       commands:
         - start_pause
         - dock
   ```

If controls are missing, check supported_features, availability and card features first. Ambiguous/stale activity can affect start_pause presentation. Do not create another entity or change unique_id to work around it.

## Regression testing and references

The separate native-controls proposal tests flags/identity, RLM2 filtering, existing state mappings, PIN/secondary pause, awaiting send before refresh, API errors and no optimistic state. Coordinator tests cover no retry on ambiguous results and bounded retry on refused login. Those tests use mocks/stubs; they do not validate frontend/service registration inside real HA.

Historical validation before separating these contributions: 292 cases passed on Python 3.14, including four cases for the subsequently withdrawn availability override. The temporary venv used only existing requirements-dev.txt dependencies; pytest-asyncio reported an unset loop-scope deprecation warning. CI uses Python 3.13, which was not run locally. After withdrawing the availability override and its four cases, the native-controls branch passed **288 tests** using `python -m pytest -q --ignore=tests/test_login_live.py`; `git diff --check` also passed. Its net diff against main contains only regression tests. The initial audit had no runnable pytest installation.

Official references consulted during native-control review: [entity contract](https://contributors.home-assistant.io/core/entities/lawn-mower/), [actions and states](https://www.home-assistant.io/integrations/lawn_mower/), [card features](https://www.home-assistant.io/dashboards/features/#lawn-mower-commands). No verification contacted Cramer services.
