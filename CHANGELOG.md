# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-05-25

### Added
- Initial release
- Mower state sensor (13 states: mowing, charging, parked, error, etc.)
- Battery level sensor
- Automatic GUC token refresh with fallback re-authentication
- Config flow UI (email + password)
- Support for RLM1 and RLM2 robotic lawn mowers
- 30-second polling via `DataUpdateCoordinator`
