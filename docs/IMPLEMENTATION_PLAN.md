# Incremental contribution roadmap

[Index](README.md) · [Open questions](OPEN_QUESTIONS.md)

Preserve the existing client, platforms, entity IDs and services. Discuss large changes in an issue, as requested by the project README. Each PR should provide source evidence and synthetic fixtures. Automated tests must not operate a physical robot.

## Contribution structure and conventions

Research belongs in a documentation-only branch (`docs/cramer-api-research`), separate from native-control regression tests (`feat/native-lawn-mower-controls`). Do not bundle root agent instructions into an upstream feature proposal. Keep documentation and contribution text in English. Preserve asynchronous shared aiohttp sessions, DataUpdateCoordinator, config entries, unique_id values and platform boundaries. Keep service schemas/translations consistent.

The working fork is `https://github.com/davidpicon7/cramer-hacs.git` (origin); the community repository is `https://github.com/claesmathias/cramer-hacs.git` (upstream). Publish authorized branches to the fork for GitHub review. Do not commit APKs/decompiled sources, credentials, PINs, PSKs or location data.

## PR 1 — Authentication error handling and privacy

Classify an account as consumer only after a valid classification response. Distinguish network/5xx failures from invalid credentials. Propagate datapoint 401 instead of empty success, with an explicit whole-refresh versus per-device degradation policy. Remove command payloads from logs and sanitize HTTP error bodies; the logging fix can be an independent urgent PR.

Dependencies: none. Risk: changing Fleet partial degradation; retain read-only operation without MQTT where appropriate. Acceptance: classification outage does not trigger consumer login; datapoint 401 invokes recovery once; synthetic PIN/token markers never appear in logs. Tests: mocked 401/403/429/5xx, timeout, malformed JSON and multiple devices, without external networking.

## PR 2 — API client and session lifecycle

Retain returned Xlink expiration, model available Fleet expiration and serialize concurrent reauthentication. Add Xlink refresh only after confirming rotation/consumption and its relationship with authorize. Do not invent GUC renewal. Add justified concurrency/timeouts and validate timer/integer bounds before packing.

Dependencies: PR 1 and sanitized contract fixtures. Risks: partially renewed credentials, lost control or excessive login. Acceptance: per-session expiry tested with a simulated clock, one concurrent renewal, terminal auth failure requests reauth and transient failure becomes UpdateFailed. Test boundaries/races and the minimal MQTT protocol with a loopback broker; preserve certificate validation.

## PR 3 — Confirmed controls and secondary-area mowing

Distinguish broker delivery from execution; investigate RLM1 MQTT responses before promising device acknowledgements. Add a small secondary-area service only after duration/PIN bounds and replies are understood. Existing start/pause/dock must not be duplicated.

Dependencies: PRs 1–2 and UI/caller/reply reconstruction. Risks: model/firmware variation and duplicate commands after timeout. Acceptance: payload agrees with Java/Smali, inputs/product/PIN are validated and ambiguous results never trigger blind retry. Test synthetic bytes and simulated device rejection. Physical tests require separate authorization and controlled conditions.

## PR 4 — Validate the existing native lawn_mower

Add regression tests for native flags/methods and shared button commands. Verify lifecycle/availability using real HA in a test environment, retaining unique_id and services. Review RETURNING fallback, unknown devices, additions/removals and stale state. Review coordinator-based availability as a separate behavior change, not a prerequisite for START/PAUSE/DOCK. Do not promise RLM2 cloud controls or replace the integration.

Dependencies: PRs 1–3 where relevant. Risks: accidental entity migration and HA version differences. Acceptance: real setup/unload/reauth/options tests for that layer, same RLM1 entities after upgrade, no unproven RLM2 controls and correct coordinator failure presentation. Establish minimum HA version with evidence before changing manifest; validate HACS/Hassfest.

## PR 5 — Sensors, diagnostics and robustness

Redact sensitive fields recursively in raw/datapoints with synthetic nested-token/location fixtures. Review calendar/DST/robot time zone, stale values and data types/units. Persistent MQTT events deserve a later PR after topics, correlation, reconnect and shutdown are reconstructed; retain polling for recovery if justified.

Dependencies: data contracts and PRs 1–2. Risks: hiding useful diagnostics or inventing values for missing data. Acceptance: absent is distinct from zero, privacy tested, explicit offline semantics, correct units and serializable diagnostic download. Test partial/malformed data, redaction, DST and partial failures; keep CI green.

## Validation strategy

Run `python3 -m pytest -q --ignore=tests/test_login_live.py` in an isolated environment with the declared development requirements. Do not omit the exclusion: live tests may load credentials automatically. Existing tests use HA stubs; add focused real-HA tests rather than replacing the entire suite. CI uses Python 3.13. Static review does not establish compatibility with every current HA version. Never introduce a new production dependency or rewrite the integration merely to simplify these contributions.
