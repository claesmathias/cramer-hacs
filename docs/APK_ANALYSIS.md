# Android application: interoperability findings

[Index](README.md) · [Authentication](AUTHENTICATION.md)

## Purpose and evidence

The local Android application analysis was used to cross-check the authentication, telemetry and RLM1 command contracts needed by the existing Home Assistant integration. This document summarizes those findings without reproducing decompiled code or a map of the application's internal packages, classes and methods.

**CONFIRMED IN CODE** refers to static evidence, not successful server requests or physical execution. Extracted APK, JADX and Apktool artifacts remain local and excluded from Git. Detailed extraction locators belong in local research notes; public references favor the integration's own source.

## Authentication and telemetry

The examined account flows distinguish Fleet and consumer users, obtain session credentials and retrieve subscribed devices and datapoints. [Authentication](AUTHENTICATION.md) describes the relevant flows and their limits. The existing client normalizes data into `CramerAuth` and `CramerDevice`; [API reference](API_REFERENCE.md) records the contracts used by HACS.

Datapoint values can contain nested JSON request/response objects. The documented datapoint table maps the existing Python parser; not every field has independently been validated against Android models or real responses.

## RLM1 MQTT

**CONFIRMED IN CODE:** the examined RLM1 controls publish binary commands over MQTT/TLS. The transport, authentication and payload formats already implemented in `api.py` and `const.py` are documented in [API reference](API_REFERENCE.md#rlm1-command-transport).

The cross-check covered start/resume, pause, return/park, weekly schedules, nonstop mowing and clock synchronization. Selected start/pause literals were also checked against local Smali output. This checks those literals, not every control-flow branch or firmware variant.

A broker acknowledgement establishes receipt, not robot execution. Device-level results and live telemetry subscriptions need further interoperability work before HACS can rely on them.

## RLM2 compatibility boundary

**CONFIRMED IN CODE:** the examined RLM2 control flows use Bluetooth with an authentication mechanism. HACS does not implement those controls. This observation does not establish that every RLM2 model or firmware lacks cloud control.

BLE key retrieval, pairing, cryptographic framing, GATT identifiers and command bytes are outside the current integration scope and are not specified here. Any future BLE contribution needs a defined interoperability requirement and authorized validation of authentication, framing and device responses.

## Scope and limits

Manufacturer support services, unrelated backend operations, firmware upload and advanced settings are outside this public reference. Their presence in the app does not establish a need to implement or document them for Home Assistant.

The extraction has decompilation warnings and errors. Conclusions must not depend on incomplete methods without a local cross-check. No server acceptance, security assessment or universal model compatibility is established by this static analysis.
