# Android application: code and communication map

[Index](README.md) · [Authentication](AUTHENTICATION.md)

## Entry point and packages

`reverse_engineering/apktool/AndroidManifest.xml:1`: package com.cramer.tools; application com.example.gelibo.FamilyApplication (30). Permissions include INTERNET (2), BLUETOOTH_CONNECT (9), SCAN (12), legacy Bluetooth and ADVERTISE (23–25). Permissions alone do not prove protocol use.

The main product namespace is **com.greenworks**, while com.cramer.tools contains R resources. Investigation followed basefunction (UI/repositories/models/API), baseframework (HTTP/MQTT/BLE), rlm1 and rlm2. AndroidX, Kotlin, Retrofit and generated resource classes were not read indiscriminately.

## Important classes and call traces

Paths are relative to sources/.

| File | Class/method | Evidence |
|---|---|---|
| com/greenworks/basefunction/repository/LoginRepository.java | isFleetUser, fleetLogin, login, gucLoginUrlEncoded, refresh | Actual login parameters; see AUTHENTICATION |
| com/greenworks/basefunction/api/ApiService.java | fleetLogin, login, gucLoginUrlEncoded, getDeviceStatus, refresh | Retrofit declarations and response types |
| com/greenworks/baseframework/http/network/NetworkApi.java | Service configuration | Production hosts:27–47; APPconfig development defaults are not production evidence |
| com/greenworks/baseframework/http/network/interceptor/RequestInterceptor.java | intercept | Headers and bearer selection:20–48 |
| com/greenworks/baseframework/http/network/interceptor/ResponseInterceptor.java | intercept | HTTP 401 → LogoutEvent |
| com/greenworks/baseframework/utils/MqttManager.java | messageArrived, publishToTopic, mqtt_init_Connect | $6 updates DpUtils/events:55–66; $8 results:71–81; publish:146–156; MD5 credentials:297–301 |
| com/greenworks/rlm1/ui/fragment/RLM1HomeFragment.java | initView/lambdas, showParkTimeDialog, showSecondaryAreaDialog | Start:681–704; pause:866–882; stop secondary:937; park:1126–1128; start secondary:1261–1263 |
| com/greenworks/rlm1/ui/activity/ScheduleEditActivity.java | saveCheck, save | Validation:474+; weekly publication:576 |
| com/greenworks/rlm1/ui/fragment/RLM1ScheduleFragment.java | initMqttData and dialogs | Responses:220–228; cancel nonstop:320; clock:575; nonstop:691 |
| com/greenworks/rlm2/ui/fragment/RLM2HomeFragment.java | sendConnect, sendCmdData | Connection:1122+; handshake:1145+; commands:1306–1410 |
| com/greenworks/baseframework/fastble/utils/RLM2BluetoothUtils.java | bleNotify, sendCmdData | GATT notify/write:23–51 |
| com/greenworks/baseframework/http/WebsocketBuilderV2.java | constructor, onConnected, completeCommand | Bearer GUC:62; remote methods:175–243 |

## RLM1 MQTT

**CONFIRMED IN CODE:** APPconfig (18,26) configures ssl://mqtt.globetools.systems:1884. MqttManager uses user_id and MD5(user_id concatenated with authorize) as username/password. It publishes decoded hexadecimal bytes, default QoS 1. UI commands target `$7/<device_id>`. Receivers recognize `$6`, `$8`, `$y`, `$g` and `$d`; full subscription topics and authorization scope have not all been reconstructed.

Start/resume uses e400; pause e200; park e600; secondary area da01; countdown 4a01; schedule 4001; clock 9a00. Full prefixes are in API_REFERENCE. Publication success does not establish firmware acceptance. UI listeners also process replies for state/error handling.

## RLM2 Bluetooth

**CONFIRMED IN CODE:** sendCmdData selects StartMowerRequest (requestType 0/1), ParkMowerRequest (3), StartMowingSecondaryAreaRequest (4) and PauseMowerRequest (6/9). Commands pass through BleConnectDelegate.buildRlm2NormalCmd and RLM2BluetoothUtils.sendCmdData. Notify/write use service `0000fd42-0000-1000-8000-00805f9b34fb` and characteristic `29bf1214-539d-4561-8509-95dcc427cf9f`.

**INFERRED:** these investigated controls require BLE proximity. This does not prove that all RLM2 firmware lacks cloud control. **PENDING REAL-WORLD VALIDATION:** full PSK authentication, encryption, fragmentation and reconnection. Do not implement only inner command bytes or send RLM1 MQTT packets over BLE without reconstructing the framing.

## SignalR/WebSocket

**CONFIRMED IN CODE:** APPconfig.BaseSignalRAddress:27 is https://signalr.globetools.systems:446/mowerSupport. WebsocketBuilderV2 constructs WebSocketHubConnectionP2 with Bearer GUC. It invokes JoinSupportHub/LeaveSupportHub with CaseId, BroadcastClientStatus, BroadcastGeneralValue, and CompleteCommand with RequestMessageId/SerialNumber/DeviceType/StatusCode/Data.

**INFERRED:** a support channel organized by case, distinct from ordinary MQTT controls. Do not replace polling until events, lifecycle and permissions are reconstructed. Negotiation and live transport have not been tested.

## Models and JSON

ApiService uses Call/Flowable, LoginBean, FleetLoginBean, GucTolenBean, XlinkTolenBean, DeviceBean and BaseResponse wrappers. LoginRepository uses Gson for bodies/errors. HACS normalizes into CramerDevice. Datapoint value is often another JSON string containing request/response. API_REFERENCE maps the existing parser; not every backend datapoint has independently been checked against Android beans.

## Smali cross-check and limits

RLM1HomeFragment start/pause literals were compared with `reverse_engineering/apktool/smali_classes3/com/greenworks/rlm1/ui/fragment/RLM1HomeFragment.smali`, lines 1289/7369 and 1648/6915 respectively. They match Java and HACS. This verifies literals, not every control-flow branch. JADX reports a type-inference warning at setDisConnectTime (Java:284); protocol conclusions do not rely on it. The main examined methods did not contain a Method not decompiled stub. The reported 102 global decompilation errors do not establish missing functionality. Future incomplete methods must be followed through Smali and anonymous classes before proposing commands.
