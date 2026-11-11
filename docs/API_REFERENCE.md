# API and communication reference

[Index](README.md) · [Android evidence](APK_ANALYSIS.md)

Scope: authentication, device inventory/state, robot controls and related communications. Commercial/account-management/vehicle APIs are not exhaustively catalogued. Contracts below are **CONFIRMED IN CODE** unless stated otherwise; current server acceptance is **PENDING REAL-WORLD VALIDATION**. Implemented means code exists, not a successful physical test.

## Hosts and common authentication

| Alias | Base URL from NetworkApi.java:27–47 |
|---|---|
| Fleet | https://cramerfleetapi.globetools.systems |
| IsFleet | https://cramerfleetauth.globetools.systems |
| Xlink | https://xapi.globetools.systems |
| GUC | https://guc.globetools.systems:446 |
| Device DB | https://device.globetools.systems |
| Products | https://productservice.globetools.systems |

Common headers: ApplicationKey, Brand, App-Name, Language. Xlink session headers: Access-Token, Xlink-Access-Token, Xlink-User-Id and Bearer GUC when available. Fleet uses Bearer Fleet. Sending is evidenced; mandatory status of each header has not been isolated experimentally. Sensitive header values are omitted.

ApiService means com/greenworks/basefunction/api/ApiService.java; LoginRepository is under basefunction/repository. Python client methods are in custom_components/cramer_connect/api.py. Response field lists describe known fields, not exhaustive server schemas.

## Classify account

- Purpose: Choose Fleet or consumer.
- HTTP method/communication: POST.
- Endpoint: `IsFleet /api/Authorization/user-exist`.
- Authentication: No initial user token; common headers.
- Known parameters: JSON username.
- Expected response: IsFleetUserBean; HACS reads existsOnFleet.
- Source file/method: ApiService.isFleetUser:387–388; LoginRepository.isFleetUser:85–88.
- Confidence: CONFIRMED IN CODE for the declaration; unknown fields and live behavior remain PENDING REAL-WORLD VALIDATION.
- HACS status: _is_fleet_user; implemented, but failures become consumer.

## Fleet login

- Purpose: Obtain session and organization.
- HTTP method/communication: POST.
- Endpoint: `Fleet /api/Authenticate`.
- Authentication: Account credentials and common headers.
- Known parameters: JSON username,password.
- Expected response: FleetLoginBean: access_token,organization_id,owner_organization_id,expiration and other metadata.
- Source file/method: ApiService.fleetLogin:190–191; LoginRepository.fleetLogin:52–57.
- Confidence: CONFIRMED IN CODE for the declaration; unknown fields and live behavior remain PENDING REAL-WORLD VALIDATION.
- HACS status: _fleet_login; expiration is not consumed.

## Fleet GUC exchange

- Purpose: Obtain GUC session.
- HTTP method/communication: POST.
- Endpoint: `Fleet /api/account/GucToken`.
- Authentication: Bearer Fleet.
- Known parameters: JSON organizationId.
- Expected response: GucTolenBean; HACS reads accessToken,refreshToken,expireIn.
- Source file/method: ApiService.getGucToken:263–264; LoginRepository.getGucToken:65–69.
- Confidence: CONFIRMED IN CODE for the declaration; unknown fields and live behavior remain PENDING REAL-WORLD VALIDATION.
- HACS status: _get_guc_token; implemented.

## Fleet Xlink exchange

- Purpose: Obtain datapoint and MQTT access.
- HTTP method/communication: POST.
- Endpoint: `Fleet /api/account/XlinkToken`.
- Authentication: Bearer Fleet.
- Known parameters: JSON organizationId.
- Expected response: XlinkTolenBean; HACS reads token,xlinkId,authString.
- Source file/method: ApiService.switchOrganization:469–470; LoginRepository.switchOrganization:59–63.
- Confidence: CONFIRMED IN CODE for the declaration; unknown fields and live behavior remain PENDING REAL-WORLD VALIDATION.
- HACS status: _get_fleet_xlink_token; optional failure.

## Consumer Xlink login

- Purpose: Obtain Xlink session.
- HTTP method/communication: POST.
- Endpoint: `Xlink /v2/user_auth`.
- Authentication: Account credentials.
- Known parameters: JSON corp_id,email,password,resource=null,phone=null,phone_zone=null.
- Expected response: LoginBean: access_token,user_id,authorize,refresh_token,expire_in.
- Source file/method: ApiService.login:390–392; LoginRepository.login:91–130.
- Confidence: CONFIRMED IN CODE for the declaration; unknown fields and live behavior remain PENDING REAL-WORLD VALIDATION.
- HACS status: _xlink_login; expire_in is not retained.

## Direct GUC login

- Purpose: Obtain consumer GUC session.
- HTTP method/communication: POST form; Android also has multipart fallback.
- Endpoint: `GUC /connect/token`.
- Authentication: Application client and account credentials; secrets omitted.
- Known parameters: scope,grant_type=password,client_id,client_secret,username,password,HasLocationInfo,Latitude,Longitude,LoginTime.
- Expected response: LoginBean: access_token,refresh_token,expires_in.
- Source file/method: ApiService.gucLogin/gucLoginUrlEncoded:376–382; LoginRepository.gucLoginUrlEncoded:175+.
- Confidence: CONFIRMED IN CODE for the declaration; unknown fields and live behavior remain PENDING REAL-WORLD VALIDATION.
- HACS status: _guc_direct_login; form only.

## Renew Xlink session

- Purpose: Renew without account password.
- HTTP method/communication: POST.
- Endpoint: `Xlink /v2/user/token/refresh`.
- Authentication: Session refresh_token; existing interceptor headers.
- Known parameters: JSON refresh_token.
- Expected response: LoginBean; full rotation/consumption semantics remain unknown.
- Source file/method: ApiService.refresh:419–421; LoginRepository.refresh:217+.
- Confidence: CONFIRMED IN CODE for the declaration; unknown fields and live behavior remain PENDING REAL-WORLD VALIDATION.
- HACS status: Not implemented; repeats login.

## List Fleet devices

- Purpose: Retrieve subscribed devices.
- HTTP method/communication: GET.
- Endpoint: `Fleet /api/devices/{orgId}/subscribed`.
- Authentication: Bearer Fleet.
- Known parameters: Path orgId.
- Expected response: ArrayList<DeviceBean>; HACS normalizes id,name,productCode,productModel,deviceStateBean and metadata.
- Source file/method: ApiService.energyBoxSubscribeFleet:179–180.
- Confidence: CONFIRMED IN CODE for the declaration; unknown fields and live behavior remain PENDING REAL-WORLD VALIDATION.
- HACS status: _get_devices_fleet; implemented.

## List Xlink devices

- Purpose: Retrieve subscribed devices.
- HTTP method/communication: GET.
- Endpoint: `Xlink /v2/user/{user_id}/subscribe/devices`.
- Authentication: Xlink session and Bearer GUC per interceptor.
- Known parameters: Path user_id.
- Expected response: ArrayList<DeviceBean>; product_id,id,is_online and metadata used by HACS.
- Source file/method: ApiService.getDevices:244–245.
- Confidence: CONFIRMED IN CODE for the declaration; unknown fields and live behavior remain PENDING REAL-WORLD VALIDATION.
- HACS status: _get_devices_xlink; implemented.

## Xlink device state

- Purpose: Read battery, state and datapoints.
- HTTP method/communication: GET.
- Endpoint: `Xlink /v2/product/{product_id}/device-state/{device_id}`.
- Authentication: Xlink session and Bearer GUC.
- Known parameters: Paths product_id,device_id.
- Expected response: DeviceStatusBean; HACS expects {datapoints:{id:{value,report_time}}}.
- Source file/method: ApiService.getDeviceStatus:232–233.
- Confidence: CONFIRMED IN CODE for the declaration; unknown fields and live behavior remain PENDING REAL-WORLD VALIDATION.
- HACS status: _get_xlink_device_state; implemented, 401 not propagated.

## Fleet device state

- Purpose: Read organization-scoped device status.
- HTTP method/communication: GET.
- Endpoint: `Fleet /api/devices/{organizationId}/status/{productId}/{deviceId}`.
- Authentication: Bearer Fleet.
- Known parameters: Paths organizationId,productId,deviceId.
- Expected response: DeviceStatusBean; dynamic response not server-validated.
- Source file/method: ApiService.getDeviceStatus:235–236.
- Confidence: CONFIRMED IN CODE for the declaration; unknown fields and live behavior remain PENDING REAL-WORLD VALIDATION.
- HACS status: get_device_status exists; ordinary enrichment uses Xlink.

## Retrieve RLM2 PSK

- Purpose: Prepare BLE access.
- HTTP method/communication: POST.
- Endpoint: `Xlink /v2/service/rlm2/device/psk`.
- Authentication: Session context; precise requirements unknown.
- Known parameters: getPsk() declares no parameters or @Body.
- Expected response: Call<PskBean>; fields not reconstructed; sensitive material must not be exported.
- Source file/method: ApiService.getPsk:315–316.
- Confidence: CONFIRMED IN CODE for the declaration; unknown fields and live behavior remain PENDING REAL-WORLD VALIDATION.
- HACS status: Not implemented.

## Write Xlink datapoint

- Purpose: Declared REST datapoint operation.
- HTTP method/communication: POST.
- Endpoint: `Xlink /v2/product/{product_id}/app_datapoint_value`.
- Authentication: Xlink session per interceptor.
- Known parameters: Path product_id; RequestBody caller/payload still to reconstruct.
- Expected response: Call<Object>; reply semantics unknown.
- Source file/method: ApiService.putAppDatapoint:415–417.
- Confidence: CONFIRMED IN CODE for the declaration; unknown fields and live behavior remain PENDING REAL-WORLD VALIDATION.
- HACS status: Not implemented; no evidence it replaces MQTT start/pause.

## Write Fleet datapoint

- Purpose: Declared organization-scoped datapoint operation.
- HTTP method/communication: POST.
- Endpoint: `Fleet /api/devices/{organizationId}/datapoint/{productId}/device/{deviceId}`.
- Authentication: Bearer Fleet.
- Known parameters: Paths as shown; RequestBody not reconstructed.
- Expected response: Call<Object>; reply semantics unknown.
- Source file/method: ApiService.putAppDatapoint:411–413.
- Confidence: CONFIRMED IN CODE for the declaration; unknown fields and live behavior remain PENDING REAL-WORLD VALIDATION.
- HACS status: Not implemented; declaration alone does not justify enabling controls.

## RLM1 command transport

MQTT 3.1.1 over TLS to mqtt.globetools.systems:1884. Topic `$7/{device_id}`, QoS 1, raw binary payload decoded from hex (not hex text or JSON). Username: Xlink user_id. Password: MD5(user_id + authorize). Source: MqttManager.publishToTopic:146–156 and mqtt_init_Connect:292–306; HACS send_command/_mqtt_publish.

All command operations below use this transport/authentication and receive a broker PUBACK, not device execution confirmation. Their Android paths are under com/greenworks/rlm1/ui/ unless another package is specified.

### Start/resume

- Purpose: Start normal mowing or resume after pause.
- Communication: MQTT/TLS using the topic and authentication above.
- Remote method/payload: `0007000d003a6000A007e400040000 + PIN_LE16`; + denotes concatenation.
- Known parameters: Zero PIN unless required; security levels 1/9 require PIN.
- Expected response: broker PUBACK; robot response handling is not implemented in HACS.
- Source file/method: fragment/RLM1HomeFragment:681–704; baseframework/utils/StringUtils.getPin:560.
- Confidence: CONFIRMED IN CODE; execution PENDING REAL-WORLD VALIDATION.
- HACS status: build_start_command; native entity and button.

### Pause

- Purpose: Stop mowing in place.
- Communication: MQTT/TLS using the topic and authentication above.
- Remote method/payload: `0007000b00386000A005e200020000`; + denotes concatenation.
- Known parameters: No variable fields.
- Expected response: broker PUBACK; robot response handling is not implemented in HACS.
- Source file/method: fragment/RLM1HomeFragment:866–882.
- Confidence: CONFIRMED IN CODE; execution PENDING REAL-WORLD VALIDATION.
- HACS status: build_stop_command; native entity and button.

### Stop secondary-area mowing

- Purpose: Cancel the secondary-area countdown.
- Communication: MQTT/TLS using the topic and authentication above.
- Remote method/payload: `0007000c00366000A0064a0103000000`; + denotes concatenation.
- Known parameters: HACS selects this variant for state 12.
- Expected response: broker PUBACK; robot response handling is not implemented in HACS.
- Source file/method: fragment/RLM1HomeFragment:937.
- Confidence: CONFIRMED IN CODE; execution PENDING REAL-WORLD VALIDATION.
- HACS status: build_stop_command; implemented.

### Return/park

- Purpose: Return to base and remain parked.
- Communication: MQTT/TLS using the topic and authentication above.
- Remote method/payload: `0007000b003e6000A005e60002 + minutes_LE16`; + denotes concatenation.
- Known parameters: 0xfffe means indefinite; duration in minutes; HACS range 1–65533.
- Expected response: broker PUBACK; robot response handling is not implemented in HACS.
- Source file/method: fragment/RLM1HomeFragment.showParkTimeDialog:1126–1128.
- Confidence: CONFIRMED IN CODE; execution PENDING REAL-WORLD VALIDATION.
- HACS status: build_park_command; dock, buttons and park service.

### Weekly schedule

- Purpose: Write the entire week.
- Communication: MQTT/TLS using the topic and authentication above.
- Remote method/payload: `0007004f00326000A049400146 + week`; + denotes concatenation.
- Known parameters: Monday first; 7 days × 2 timers × (hour,minute,duration_LE16,mode); mode 1 active.
- Expected response: broker PUBACK; robot response handling is not implemented in HACS.
- Source file/method: activity/ScheduleEditActivity.save:556–576.
- Confidence: CONFIRMED IN CODE; execution PENDING REAL-WORLD VALIDATION.
- HACS status: build_schedule_command; set_schedule and read-only calendar.

### Nonstop mowing

- Purpose: Temporarily ignore schedule or cancel override.
- Communication: MQTT/TLS using the topic and authentication above.
- Remote method/payload: `0007000c00366000A0064a0103 + minutes_LE16 + mode`; + denotes concatenation.
- Known parameters: 1–24 days converted to minutes, mode 01; cancellation suffix 000000.
- Expected response: broker PUBACK; robot response handling is not implemented in HACS.
- Source file/method: fragment/RLM1ScheduleFragment:320,691.
- Confidence: CONFIRMED IN CODE; execution PENDING REAL-WORLD VALIDATION.
- HACS status: build_nonstop_command; existing services.

### Set clock

- Purpose: Synchronize clock and UTC offset.
- Communication: MQTT/TLS using the topic and authentication above.
- Remote method/payload: `0007001100566000A00b9a0008 + epoch_LE32 + offset_LE32`; + denotes concatenation.
- Known parameters: UTC epoch seconds; signed offset seconds.
- Expected response: broker PUBACK; robot response handling is not implemented in HACS.
- Source file/method: fragment/RLM1ScheduleFragment:575; baseframework/utils/StringUtils.getEightLen:565.
- Confidence: CONFIRMED IN CODE; execution PENDING REAL-WORLD VALIDATION.
- HACS status: build_set_clock_command; service and button.

### Start secondary area

- Purpose: Start mowing a secondary area.
- Communication: MQTT/TLS using the topic and authentication above.
- Remote method/payload: `0007000d003c6000A007da0104 + minutes_LE16 + PIN_LE16`; + denotes concatenation.
- Known parameters: UI-selected duration; PIN conditional on security; UI bounds still to verify.
- Expected response: broker PUBACK; robot response handling is not implemented in HACS.
- Source file/method: fragment/RLM1HomeFragment.showSecondaryAreaDialog:1261–1263.
- Confidence: CONFIRMED IN CODE; execution PENDING REAL-WORLD VALIDATION.
- HACS status: Not implemented; candidate after bounds/reply validation.

## MQTT events

- Purpose: receive datapoints and command results.
- Communication/endpoint: MQTT callbacks recognize topic prefixes $6/$8; complete subscription topics remain unknown.
- Authentication: the MQTT session described above.
- Known parameters: device extracted from topic; payload handled by MqttResultBuilder/DpUtils.
- Expected response: $6 creates PublishEvent/MQTT_REFRESH_DPS; $8 can create VEHICLE_MQTT_SET_DP_RESULT. Do not attribute every vehicle result to RLM1.
- Source file/method: baseframework/utils/MqttManager.mqttCallback.messageArrived:55–81.
- Confidence: CONFIRMED IN CODE; model-specific correlation PENDING REAL-WORLD VALIDATION.
- HACS status: absent; polling and PUBACK only.

## RLM2 BLE controls

- Purpose: start, pause and park locally.
- Communication/endpoint: GATT notify/write; UUIDs are listed in APK_ANALYSIS.
- Remote method: RLM2HomeFragment.sendCmdData → BleConnectDelegate.buildRlm2NormalCmd → RLM2BluetoothUtils.sendCmdData.
- Authentication: complete handshake/PSK reconstruction pending.
- Known parameters: clientId and inner command. Start 000be4000400000000 (PIN replaces tail when required); pause 0009e200020000; park 0009e60002 + duration_LE16, feff for indefinite.
- Expected response: BLE notifications/requestMap validation; not fully reconstructed.
- Source file/method: rlm2/ui/fragment/RLM2HomeFragment.sendCmdData:1306–1375; baseframework/fastble/utils/RLM2BluetoothUtils:23–51.
- Confidence: CONFIRMED IN CODE for these call paths; framing/security PENDING REAL-WORLD VALIDATION.
- HACS status: absent; do not promise RLM2 cloud compatibility.

## SignalR support hub

- Purpose: support by CaseId, INFERRED from methods/data.
- Communication/endpoint: SignalR/WebSocket; APPconfig.BaseSignalRAddress is https://signalr.globetools.systems:446/mowerSupport.
- Remote methods: JoinSupportHub, LeaveSupportHub, BroadcastClientStatus, BroadcastGeneralValue, CompleteCommand.
- Authentication: Bearer GUC passed to WebSocketHubConnectionP2.
- Known parameters: Join/Leave use CaseId/SenderInfo; broadcasts use MessageId/Data; CompleteCommand adds SerialNumber, DeviceType=3, StatusCode, Message, Data, RequestMessageId.
- Expected response: hub events; complete contract unknown. Distinct from MQTT acknowledgements.
- Source file/method: baseframework/http/WebsocketBuilderV2 constructor:59–64; broadcast methods:175–196; leaveSupportHub:199–204; completeCommand:207–218; onConnected:238–243.
- Confidence: CONFIRMED IN CODE for invocations; live transport/scope PENDING REAL-WORLD VALIDATION.
- HACS status: absent; not established as a general telemetry channel.

## Datapoints parsed by HACS

Direct evidence: api.py._get_xlink_device_state, approximately lines 680–900. This maps the existing parser, not independently verified Android fields or real server responses.

| DP | Expected value structure | Use |
|---|---|---|
| 8 | response.security_level,return_code | PIN requirement |
| 21 | response.mower_name | Model; strip NUL suffix |
| 31/36 | response.signal_quality/gprs_lte_signal_quality | WiFi/mobile strength |
| 32 | request.mower_main_state,battery_status,next_start,source_for_next_start | State/battery/next start; report_time outside value |
| 33 | request.event_id,request_time | Last error |
| 34 | request.latitude,longitude | GPS |
| 48 | response.cutting_time,running_time,charging_time,no_of_fatal_error | Statistics |
| 117 | request.mower_main_application_*; response.sw_update | Installed version/update flag |
| 119 | response.program_header, hexadecimal | Offered firmware header/version |
| 125 | response.<weekday>_timer_<1/2>_<field> | Schedule; return_code=0 |
| 225 | Direct hexadecimal string | Distance in metres |
| 246 | Direct string | Fallback software version |

Current numeric states 0–12: starting up, physical stop, parked, paused, mowing, leaving base, returning, charging, error, fatal error, recovery, alarm, secondary-area mowing. Parking reasons are a separate dimension, source_for_next_start. Preserve raw_state rather than flattening it away. Missing datapoints must not become zero. HACS excludes next_start sentinels 0/-1/0xffffffff.
