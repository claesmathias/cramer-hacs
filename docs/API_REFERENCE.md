# API and communication reference

[Index](README.md) · [Android evidence](APK_ANALYSIS.md)

Scope: contracts used by the existing integration for authentication, device inventory/state and RLM1 controls. Unimplemented backend operations and manufacturer support services are outside this reference. Contracts below are **CONFIRMED IN CODE** unless stated otherwise; current server acceptance is **PENDING REAL-WORLD VALIDATION**. Implemented means code exists, not a successful physical test.

## Hosts and common authentication

| Alias | Base URL declared in HACS const.py |
|---|---|
| Fleet | https://cramerfleetapi.globetools.systems |
| IsFleet | https://cramerfleetauth.globetools.systems |
| Xlink | https://xapi.globetools.systems |
| GUC | https://guc.globetools.systems:446 |

Common headers: ApplicationKey, Brand, App-Name, Language. Xlink session headers: Access-Token, Xlink-Access-Token, Xlink-User-Id and Bearer GUC when available. Fleet uses Bearer Fleet. Sending is evidenced; mandatory status of each header has not been isolated experimentally. Sensitive header values are omitted.

Python client methods are in `custom_components/cramer_connect/api.py`; transport and command constants are in `const.py` in the same directory. Response field lists describe known fields, not exhaustive server schemas.

## Classify account

- Purpose: Choose Fleet or consumer.
- HTTP method/communication: POST.
- Endpoint: `IsFleet /api/Authorization/user-exist`.
- Authentication: No initial user token; common headers.
- Known parameters: JSON username.
- Expected response: HACS reads existsOnFleet.
- Integration source: `api.py::_is_fleet_user`.
- Confidence: CONFIRMED IN CODE in the integration; unknown fields and live behavior remain PENDING REAL-WORLD VALIDATION.
- HACS status: _is_fleet_user; implemented, but failures become consumer.

## Fleet login

- Purpose: Obtain session and organization.
- HTTP method/communication: POST.
- Endpoint: `Fleet /api/Authenticate`.
- Authentication: Account credentials and common headers.
- Known parameters: JSON username,password.
- Expected response fields: access_token,organization_id,owner_organization_id,expiration and other metadata.
- Integration source: `api.py::_fleet_login`.
- Confidence: CONFIRMED IN CODE in the integration; unknown fields and live behavior remain PENDING REAL-WORLD VALIDATION.
- HACS status: _fleet_login; expiration is not consumed.

## Fleet GUC exchange

- Purpose: Obtain GUC session.
- HTTP method/communication: POST.
- Endpoint: `Fleet /api/account/GucToken`.
- Authentication: Bearer Fleet.
- Known parameters: JSON organizationId.
- Expected response: HACS reads accessToken,refreshToken,expireIn.
- Integration source: `api.py::_get_guc_token`.
- Confidence: CONFIRMED IN CODE in the integration; unknown fields and live behavior remain PENDING REAL-WORLD VALIDATION.
- HACS status: _get_guc_token; implemented.

## Fleet Xlink exchange

- Purpose: Obtain datapoint and MQTT access.
- HTTP method/communication: POST.
- Endpoint: `Fleet /api/account/XlinkToken`.
- Authentication: Bearer Fleet.
- Known parameters: JSON organizationId.
- Expected response: HACS reads token,xlinkId,authString.
- Integration source: `api.py::_get_fleet_xlink_token`.
- Confidence: CONFIRMED IN CODE in the integration; unknown fields and live behavior remain PENDING REAL-WORLD VALIDATION.
- HACS status: _get_fleet_xlink_token; optional failure.

## Consumer Xlink login

- Purpose: Obtain Xlink session.
- HTTP method/communication: POST.
- Endpoint: `Xlink /v2/user_auth`.
- Authentication: Account credentials.
- Known parameters: JSON corp_id,email,password,resource=null,phone=null,phone_zone=null.
- Expected response fields: access_token,user_id,authorize,refresh_token,expire_in.
- Integration source: `api.py::_xlink_login`.
- Confidence: CONFIRMED IN CODE in the integration; unknown fields and live behavior remain PENDING REAL-WORLD VALIDATION.
- HACS status: _xlink_login; expire_in is not retained.

## Direct GUC login

- Purpose: Obtain consumer GUC session.
- HTTP method/communication: POST form in HACS.
- Endpoint: `GUC /connect/token`.
- Authentication: Application client and account credentials; secrets omitted.
- Known parameters: scope,grant_type=password,client_id,client_secret,username,password,HasLocationInfo,Latitude,Longitude,LoginTime.
- Expected response fields: access_token,refresh_token,expires_in.
- Integration source: `api.py::_guc_direct_login`.
- Confidence: CONFIRMED IN CODE in the integration; unknown fields and live behavior remain PENDING REAL-WORLD VALIDATION.
- HACS status: _guc_direct_login; form only.

## List Fleet devices

- Purpose: Retrieve subscribed devices.
- HTTP method/communication: GET.
- Endpoint: `Fleet /api/devices/{orgId}/subscribed`.
- Authentication: Bearer Fleet.
- Known parameters: Path orgId.
- Expected response: Device list; HACS normalizes id,name,productCode,productModel,deviceStateBean and metadata.
- Integration source: `api.py::_get_devices_fleet`.
- Confidence: CONFIRMED IN CODE in the integration; unknown fields and live behavior remain PENDING REAL-WORLD VALIDATION.
- HACS status: _get_devices_fleet; implemented.

## List Xlink devices

- Purpose: Retrieve subscribed devices.
- HTTP method/communication: GET.
- Endpoint: `Xlink /v2/user/{user_id}/subscribe/devices`.
- Authentication: Xlink session and Bearer GUC in the Python client.
- Known parameters: Path user_id.
- Expected response: Device list; product_id,id,is_online and metadata used by HACS.
- Integration source: `api.py::_get_devices_xlink`.
- Confidence: CONFIRMED IN CODE in the integration; unknown fields and live behavior remain PENDING REAL-WORLD VALIDATION.
- HACS status: _get_devices_xlink; implemented.

## Xlink device state

- Purpose: Read battery, state and datapoints.
- HTTP method/communication: GET.
- Endpoint: `Xlink /v2/product/{product_id}/device-state/{device_id}`.
- Authentication: Xlink session and Bearer GUC.
- Known parameters: Paths product_id,device_id.
- Expected response: HACS expects {datapoints:{id:{value,report_time}}}.
- Integration source: `api.py::_get_xlink_device_state`.
- Confidence: CONFIRMED IN CODE in the integration; unknown fields and live behavior remain PENDING REAL-WORLD VALIDATION.
- HACS status: _get_xlink_device_state; implemented, 401 not propagated.

## Fleet device state

- Purpose: Read organization-scoped device status.
- HTTP method/communication: GET.
- Endpoint: `Fleet /api/devices/{organizationId}/status/{productId}/{deviceId}`.
- Authentication: Bearer Fleet.
- Known parameters: Paths organizationId,productId,deviceId.
- Expected response: Device status; dynamic response not server-validated.
- Integration source: `api.py::get_device_status`.
- Confidence: CONFIRMED IN CODE in the integration; unknown fields and live behavior remain PENDING REAL-WORLD VALIDATION.
- HACS status: get_device_status exists; ordinary enrichment uses Xlink.

## RLM1 command transport

MQTT 3.1.1 over TLS to mqtt.globetools.systems:1884. Topic `$7/{device_id}`, QoS 1, raw binary payload decoded from hex (not hex text or JSON). Username: Xlink user_id. Password: MD5(user_id + authorize). Integration source: `api.py::send_command`, `api.py::_mqtt_publish` and MQTT constants in `const.py`.

All command operations below use this transport/authentication and receive a broker PUBACK, not device execution confirmation.

### Start/resume

- Purpose: Start normal mowing or resume after pause.
- Communication: MQTT/TLS using the topic and authentication above.
- Remote method/payload: `0007000d003a6000A007e400040000 + PIN_LE16`; + denotes concatenation.
- Known parameters: Zero PIN unless required; security levels 1/9 require PIN.
- Expected response: broker PUBACK; robot response handling is not implemented in HACS.
- Integration source: `api.py::build_start_command`.
- Confidence: CONFIRMED IN CODE; execution PENDING REAL-WORLD VALIDATION.
- HACS status: build_start_command; native entity and button.

### Pause

- Purpose: Stop mowing in place.
- Communication: MQTT/TLS using the topic and authentication above.
- Remote method/payload: `0007000b00386000A005e200020000`; + denotes concatenation.
- Known parameters: No variable fields.
- Expected response: broker PUBACK; robot response handling is not implemented in HACS.
- Integration source: `api.py::build_stop_command`.
- Confidence: CONFIRMED IN CODE; execution PENDING REAL-WORLD VALIDATION.
- HACS status: build_stop_command; native entity and button.

### Stop secondary-area mowing

- Purpose: Cancel the secondary-area countdown.
- Communication: MQTT/TLS using the topic and authentication above.
- Remote method/payload: `0007000c00366000A0064a0103000000`; + denotes concatenation.
- Known parameters: HACS selects this variant for state 12.
- Expected response: broker PUBACK; robot response handling is not implemented in HACS.
- Integration source: `api.py::build_stop_command`.
- Confidence: CONFIRMED IN CODE; execution PENDING REAL-WORLD VALIDATION.
- HACS status: build_stop_command; implemented.

### Return/park

- Purpose: Return to base and remain parked.
- Communication: MQTT/TLS using the topic and authentication above.
- Remote method/payload: `0007000b003e6000A005e60002 + minutes_LE16`; + denotes concatenation.
- Known parameters: 0xfffe means indefinite; duration in minutes; HACS range 1–65533.
- Expected response: broker PUBACK; robot response handling is not implemented in HACS.
- Integration source: `api.py::build_park_command`.
- Confidence: CONFIRMED IN CODE; execution PENDING REAL-WORLD VALIDATION.
- HACS status: build_park_command; dock, buttons and park service.

### Weekly schedule

- Purpose: Write the entire week.
- Communication: MQTT/TLS using the topic and authentication above.
- Remote method/payload: `0007004f00326000A049400146 + week`; + denotes concatenation.
- Known parameters: Monday first; 7 days × 2 timers × (hour,minute,duration_LE16,mode); mode 1 active.
- Expected response: broker PUBACK; robot response handling is not implemented in HACS.
- Integration source: `api.py::build_schedule_command`.
- Confidence: CONFIRMED IN CODE; execution PENDING REAL-WORLD VALIDATION.
- HACS status: build_schedule_command; set_schedule and read-only calendar.

### Nonstop mowing

- Purpose: Temporarily ignore schedule or cancel override.
- Communication: MQTT/TLS using the topic and authentication above.
- Remote method/payload: `0007000c00366000A0064a0103 + minutes_LE16 + mode`; + denotes concatenation.
- Known parameters: 1–24 days converted to minutes, mode 01; cancellation suffix 000000.
- Expected response: broker PUBACK; robot response handling is not implemented in HACS.
- Integration source: `api.py::build_nonstop_command`.
- Confidence: CONFIRMED IN CODE; execution PENDING REAL-WORLD VALIDATION.
- HACS status: build_nonstop_command; existing services.

### Set clock

- Purpose: Synchronize clock and UTC offset.
- Communication: MQTT/TLS using the topic and authentication above.
- Remote method/payload: `0007001100566000A00b9a0008 + epoch_LE32 + offset_LE32`; + denotes concatenation.
- Known parameters: UTC epoch seconds; signed offset seconds.
- Expected response: broker PUBACK; robot response handling is not implemented in HACS.
- Integration source: `api.py::build_set_clock_command`.
- Confidence: CONFIRMED IN CODE; execution PENDING REAL-WORLD VALIDATION.
- HACS status: build_set_clock_command; service and button.

### Start secondary area

Not implemented. A future contribution must establish duration bounds, authentication requirements and device response handling before adding a command contract. The existing stop-secondary-area variant remains documented above because HACS already uses it.

## MQTT events

HACS uses polling and broker PUBACK only. Device-level acknowledgements and live telemetry subscriptions remain future interoperability work. Subscription scope, response correlation and reconnect behavior must be validated before implementation.

## RLM2 BLE controls

The examined Android RLM2 controls use authenticated Bluetooth. HACS does not implement this transport. Key retrieval, pairing, GATT identifiers, framing and command bytes are outside this reference. See [compatibility boundary](APK_ANALYSIS.md#rlm2-compatibility-boundary). No universal claim about RLM2 cloud compatibility follows from the examined flows.

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
