# Open questions and verification

[Index](README.md) · [Reference](API_REFERENCE.md)

No experiments below have been performed against Cramer or hardware. Any such experiment requires separate authorization.

| Question/hypothesis | Status | Next evidence needed |
|---|---|---|
| How does GUC renew without a password? | PENDING REAL-WORLD VALIDATION; OAuth conventions are insufficient | Additional callers/Smali, then a sanitized authorized session response |
| Does Xlink refresh rotate authorize/refresh_token? | Refresh contract confirmed; policy unknown | Follow LoginRepository.refresh observers before atomic renewal design |
| What is Fleet lifetime and selected organization? | expiration field confirmed | Compare LoginActivity/organization selection and fixtures for multiple roles |
| Is every header mandatory? | Sending confirmed; requirement untested | Inspect Http as well as NetworkApi interceptors; later sanitized capture |
| Does RLM2 offer additional cloud controls? | BLE confirmed; cloud impossibility unproven | Follow app_datapoint_value callers; separate telemetry from commands |
| How do BLE handshake/encryption work? | Incomplete reconstruction | Follow BleConnectDelegate, PSK and notifications; check Smali without exposing keys |
| Which MQTT topics are subscribed, with what scope? | Receive prefixes confirmed | Follow subscribeToTopic/lifecycle; document RLM1-specific responses |
| How is command acceptance correlated? | PUBACK is insufficient | Match request_payload/return_code and UI events to transmitted frames |
| Is SignalR general telemetry or case-based support? | Support inferred | Follow WebsocketBuilderV2 creation/events without opening real support cases |
| What are secondary-area/settings limits? | Send literals confirmed | Verify UI ranges, units, safety, replies and firmware differences |
| Which datapoints apply to RLM2, and how stale are they? | HACS parser confirmed; model coverage unknown | Follow DeviceStatusBean/DpUtils; use separate synthetic model fixtures |
| Does scheduling use HA, robot or account time zone? DST? | HACS uses HA time zone | Compare Android/clock code and test DST/midnight with pure functions |
| Can diagnostics contain unknown sensitive identifiers? | Static risk | Inject markers into raw/JSON strings; verify redaction before sharing |
| Do new devices appear without reload? | Platforms create entities at setup | Real-HA addition/removal test with mocked client |

## Verification procedure

1. Search a specific symbol with rg in product packages, following caller → API → serializer/transport. Avoid indiscriminate library traversal.
2. Record path, class, method, line and APK version/hash. No APK hash was calculated in the initial audit.
3. When Java is incomplete, locate corresponding methods/anonymous classes in smali_classes*. Check literals, branches and endian conversions before inferring parameters.
4. Create minimal synthetic contract fixtures without account data. Distinguish declarations from calls in an exercised flow.
5. Only after separate authorization, compare against sanitized real responses. Keep APKs, sources, original logs, credentials, tokens, PINs, PSKs and locations out of Git. Do not bypass access controls or infer authorization for physical commands.

## Investigation limits

Not all APK classes, commercial APIs, full pairing, firmware upload or advanced settings were reconstructed. The reference marks partial contracts explicitly. No coverage percentage was measured. Initial tests could not run because pytest was missing; a later native-controls session ran unit tests in a temporary environment, as recorded in ARCHITECTURE. This documentation branch contains no code/test changes. Initial reverse engineering used no external HA references or active services; the later native-controls guide links official HA documentation. Line numbers refer to the local extraction.
