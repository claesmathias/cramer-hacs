# Feature comparison

[Index](README.md) · [Roadmap](IMPLEMENTATION_PLAN.md)

Android entries describe static call-path evidence, not universal support across models. HACS entries describe existing code.

| Feature | Android APK | Current HACS | Evidence | Priority |
|---|---|---|---|---|
| Fleet/consumer accounts | Yes | Yes; errors can misclassify accounts | LoginRepository; api._is_fleet_user | P0 |
| Xlink renewal without password | Method present | Repeats login | LoginRepository.refresh; coordinator._ensure_auth | P1 |
| Per-token expiration | expire_in/combined deadline | GUC + fixed Xlink 7200 | LoginActivity:333–377; CramerAuth | P1 |
| Inventory | Yes | Yes | ApiService.getDevices/energyBoxSubscribeFleet | Maintain |
| Battery/state/errors/GPS | Models/datapoints | Yes; 30-second polling | ApiService.getDeviceStatus; api parser | P1 robustness |
| RLM1 start/resume | MQTT | Yes | RLM1HomeFragment:681–704 | Maintain/test |
| RLM1 pause | MQTT | Yes; secondary-area variant | RLM1HomeFragment:866–937 | Maintain/test |
| Return to base | MQTT park | Yes; timed/indefinite | RLM1HomeFragment:1126–1128 | Maintain |
| Native HA lawn_mower | Not applicable | Already exists | lawn_mower.py | P1 contract validation |
| Weekly schedule | MQTT editor | Services and calendar | ScheduleEditActivity.save | P1 bounds/DST |
| Nonstop/clock | MQTT | Yes | RLM1ScheduleFragment:320,575,691 | Maintain |
| Start secondary area | MQTT | No; stop only | RLM1HomeFragment:1261–1263 | P2 |
| Live MQTT events | Callbacks | No; PUBACK/polling | MqttManager:55–81 | P2 research |
| RLM2 BLE control | Yes in examined flows | No | RLM2HomeFragment.sendCmdData | P3 |
| Remote support hub | SignalR by case | No | WebsocketBuilderV2 | P3; HA usefulness unclear |
| Installed/offered firmware | Yes; RLM2 includes BLE upload | Read-only update entity | RLM2HomeFragment:1377+; update.py | Do not prioritize writes |
| Advanced settings | WeatherGuards/Security/EditGeofence/OperatingArea classes | No general writes | rlm1/ui/activity; flows not reconstructed | P3 research |
| Private diagnostics | Not audited | Partial known-key redaction | diagnostics.py | P0 logs/P1 tests |

START_MOWING, PAUSE and DOCK need no duplicate implementation. [Native controls](NATIVE_LAWN_MOWER_CONTROLS.md) explains their existing behavior and manual checks. Device execution confirmation remains open; PUBACK acknowledges broker receipt only. Availability changes should be reviewed separately from native-control regression tests.
