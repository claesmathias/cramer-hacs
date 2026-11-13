# Feature comparison

[Index](README.md) · [Roadmap](IMPLEMENTATION_PLAN.md)

Android entries describe static call-path evidence, not universal support across models. HACS entries describe existing code.

| Feature | Android APK | Current HACS | Evidence | Priority |
|---|---|---|---|---|
| Fleet/consumer accounts | Yes | Yes; errors can misclassify accounts | LoginRepository; api._is_fleet_user | P0 |
| Xlink renewal without password | Method present | Repeats login | LoginRepository.refresh; coordinator._ensure_auth | P1 |
| Per-token expiration | expire_in/combined deadline | GUC + fixed Xlink 7200 | Android session handling; CramerAuth | P1 |
| Inventory | Yes | Yes | ApiService.getDevices/energyBoxSubscribeFleet | Maintain |
| Battery/state/errors/GPS | Models/datapoints | Yes; 30-second polling | ApiService.getDeviceStatus; api parser | P1 robustness |
| RLM1 start/resume | MQTT | Yes | RLM1 control flow | Maintain/test |
| RLM1 pause | MQTT | Yes; secondary-area variant | RLM1 control flow | Maintain/test |
| Return to base | MQTT park | Yes; timed/indefinite | RLM1 control flow | Maintain |
| Native HA lawn_mower | Not applicable | Already exists | lawn_mower.py | P1 contract validation |
| Weekly schedule | MQTT editor | Services and calendar | ScheduleEditActivity.save | P1 bounds/DST |
| Nonstop/clock | MQTT | Yes | api.build_nonstop_command/build_set_clock_command | Maintain |
| Start secondary area | MQTT | No; stop only | RLM1 control flow | P2 |
| Live MQTT events | Callbacks | No; PUBACK/polling | Android MQTT callbacks | P2 research |
| RLM2 BLE control | Yes in examined flows | No | RLM2HomeFragment.sendCmdData | P3 |
| Installed/offered firmware | Yes; RLM2 includes BLE upload | Read-only update entity | RLM2 firmware flow; update.py | Do not prioritize writes |
| Advanced settings | Settings UI present | No general writes | Flows not reconstructed | P3 research |
| Private diagnostics | Not audited | Partial known-key redaction | diagnostics.py | P0 logs/P1 tests |

START_MOWING, PAUSE and DOCK need no duplicate implementation. [Native controls](NATIVE_LAWN_MOWER_CONTROLS.md) explains their existing behavior and manual checks. Device execution confirmation remains open; PUBACK acknowledges broker receipt only. Availability changes should be reviewed separately from native-control regression tests.
