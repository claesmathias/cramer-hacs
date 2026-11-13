"""Cramer Connect API client."""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import secrets
import ssl
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import aiohttp

from .const import (
    CMD_NONSTOP_CANCEL,
    CMD_NONSTOP_PREFIX,
    CMD_SCHEDULE_PREFIX,
    CMD_SET_CLOCK_PREFIX,
    NONSTOP_MAX_DAYS,
    NONSTOP_SOURCES,
    SCHEDULE_DAYS,
    SCHEDULE_TIMERS_PER_DAY,
    CMD_PARK_PREFIX,
    CMD_START,
    CMD_START_PREFIX,
    CMD_STOP,
    CMD_STOP_SECONDARY_AREA,
    PARK_UNTIL_FURTHER_NOTICE,
    APP_APPLICATION_KEY,
    APP_BRAND,
    APP_NAME,
    FLEET_API_URL,
    FLEET_AUTH_URL,
    GUC_CLIENT_ID,
    GUC_CLIENT_SECRET,
    GUC_SCOPE,
    GUC_URL,
    MOWER_ERROR_MAP,
    MOWER_STATE_MAP,
    PARKED_REASON_STATES,
    MQTT_COMMAND_TOPIC,
    MQTT_HOST,
    MQTT_PORT,
    NEXT_START_SOURCE_MAP,
    PIN_REQUIRED_SECURITY_LEVELS,
    PRODUCT_CODE_RLM2,
    ROBOTIC_MOWER_PRODUCT_CODES,
    XLINK_CORP_ID,
    XLINK_URL,
)

# xlink access tokens are valid for 2 hours (the app hardcodes 7200 s)
XLINK_TOKEN_LIFETIME_S = 7200

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScheduleTimer:
    """One timer slot of the weekly schedule (dp[125])."""

    start_hour: int = 0
    start_minute: int = 0
    length_minutes: int = 0
    enabled: bool = False

    @property
    def active(self) -> bool:
        return self.enabled and self.length_minutes > 0

    @property
    def start_minutes(self) -> int:
        return self.start_hour * 60 + self.start_minute

    @property
    def end_minutes(self) -> int:
        return self.start_minutes + self.length_minutes


# 7 days (Monday first) x 2 timers
Schedule = tuple[tuple[ScheduleTimer, ...], ...]

OFF_TIMER = ScheduleTimer()


def parse_schedule(response: dict[str, Any]) -> Schedule | None:
    """Parse the dp[125] response object into a Schedule."""
    days = []
    for day in SCHEDULE_DAYS:
        timers = []
        for n in range(1, SCHEDULE_TIMERS_PER_DAY + 1):
            prefix = f"{day}_timer_{n}_"
            try:
                timers.append(ScheduleTimer(
                    start_hour=int(response[prefix + "start_time_hour"]),
                    start_minute=int(response[prefix + "start_time_minute"]),
                    length_minutes=int(response[prefix + "length_minutes"]),
                    enabled=int(response[prefix + "timer_mode"]) == 1,
                ))
            except (KeyError, TypeError, ValueError):
                return None
        days.append(tuple(timers))
    return tuple(days)


def validate_day_timers(timers: tuple[ScheduleTimer, ...]) -> None:
    """Apply the app's rules: within one day, end after start, no overlap."""
    for t in timers:
        if not (0 <= t.start_hour < 24 and 0 <= t.start_minute < 60):
            raise ValueError("Start time out of range")
        if not 0 <= t.length_minutes <= 24 * 60:
            raise ValueError("Timer length out of range")
    active = [t for t in timers if t.active]
    for t in active:
        if t.end_minutes > 24 * 60:
            raise ValueError("A timer must end before midnight")
    if len(active) == 2:
        a, b = sorted(active, key=lambda t: t.start_minutes)
        if b.start_minutes < a.end_minutes:
            raise ValueError("The two timers overlap")


def build_schedule_command(schedule: Schedule) -> str:
    """Full weekly schedule, as ScheduleEditActivity.save() sends it."""
    if len(schedule) != len(SCHEDULE_DAYS):
        raise ValueError("A schedule needs 7 days")
    payload = ""
    for timers in schedule:
        if len(timers) != SCHEDULE_TIMERS_PER_DAY:
            raise ValueError("Each day needs 2 timers")
        validate_day_timers(timers)
        for t in timers:
            payload += (
                f"{t.start_hour:02x}{t.start_minute:02x}"
                + _le16(t.length_minutes if t.enabled else 0)
                + ("01" if t.active else "00")
            )
    return CMD_SCHEDULE_PREFIX + payload


def build_nonstop_command(days: int | None) -> str:
    """Mow nonstop (ignoring the schedule) for `days`; None cancels."""
    if days is None:
        return CMD_NONSTOP_CANCEL
    days = int(days)
    if not 1 <= days <= NONSTOP_MAX_DAYS:
        raise ValueError(f"Nonstop mowing must be 1-{NONSTOP_MAX_DAYS} days")
    return CMD_NONSTOP_PREFIX + _le16(days * 1440) + "01"


def build_set_clock_command(utc_epoch: int, utc_offset_s: int) -> str:
    """Set the mower clock to `utc_epoch` with the local UTC offset."""
    return (
        CMD_SET_CLOCK_PREFIX
        + (int(utc_epoch) & 0xFFFFFFFF).to_bytes(4, "little").hex()
        + int(utc_offset_s).to_bytes(4, "little", signed=True).hex()
    )


@dataclass
class CramerDevice:
    device_id: str
    product_id: str
    name: str
    serial_number: str
    mac: str
    product_code: str
    state: str | None
    battery: int | None
    is_online: bool
    # Scheduled next start — Unix epoch seconds; None means no schedule
    next_start_ts: int | None = None
    # Statistics from dp[48]
    cutting_time_s: int | None = None
    running_time_s: int | None = None
    charging_time_s: int | None = None
    error_count: int | None = None
    # Distance from dp[225] (hex metres)
    distance_m: int | None = None
    # GPS from dp[34]
    latitude: float | None = None
    longitude: float | None = None
    # Software info from dp[117] / dp[246]
    software_version: str | None = None
    sw_update_available: bool | None = None
    # Hardware model from dp[21]
    mower_model: str | None = None
    # Reason for the current parked/charging state (dp[32] source_for_next_start)
    source_for_next_start: int | None = None
    # Security level from dp[8]; 1 or 9 means commands need the PIN code
    security_level: int | None = None
    # Last reported error from dp[33]
    last_error_code: int | None = None
    last_error_time: str | None = None
    # When the mower last reported its state (dp[32] report_time)
    last_seen: datetime | None = None
    # Connection quality in % (dp[31] WiFi, dp[36] mobile network)
    wifi_signal: int | None = None
    lte_signal: int | None = None
    # Firmware offered to the mower (dp[119] program header)
    latest_software_version: str | None = None
    # Weekly schedule from dp[125]
    schedule: Schedule | None = None
    # Raw datapoints from the last device-state call (for diagnostics)
    datapoints: dict[str, Any] = field(default_factory=dict)
    # Per-device xlink authorize code (from subscribe/devices response)
    device_authorize: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def state_label(self) -> str:
        """State as shown in the app; 'parked' is split into its reasons."""
        if self.state == "2" and self.source_for_next_start in PARKED_REASON_STATES:
            return PARKED_REASON_STATES[self.source_for_next_start]
        return MOWER_STATE_MAP.get(self.state or "", "unknown")

    @property
    def nonstop_mowing(self) -> bool:
        """Mowing nonstop, ignoring the schedule (until next_start)."""
        return self.source_for_next_start in NONSTOP_SOURCES

    @property
    def is_charging(self) -> bool:
        return self.state == "7" or (
            self.state == "2" and self.source_for_next_start == 1
        )

    @property
    def next_start_reason(self) -> str | None:
        """Why the mower is parked/charging (e.g. parked_by_schedule)."""
        if self.source_for_next_start is None:
            return None
        return NEXT_START_SOURCE_MAP.get(self.source_for_next_start)

    @property
    def last_error(self) -> str | None:
        """Human readable text of the last reported error."""
        if self.last_error_code is None:
            return None
        if self.last_error_code <= 0:
            return "Unknown error"
        return MOWER_ERROR_MAP.get(
            self.last_error_code, f"Error {self.last_error_code}"
        )

    @property
    def requires_pin(self) -> bool:
        return self.security_level in PIN_REQUIRED_SECURITY_LEVELS

    @property
    def supports_remote_control(self) -> bool:
        """RLM2 is controlled over Bluetooth only — no cloud commands."""
        return self.product_code != PRODUCT_CODE_RLM2

    @property
    def is_mower(self) -> bool:
        # When a productCode is known, use it to decide.
        if self.product_code:
            return self.product_code in ROBOTIC_MOWER_PRODUCT_CODES
        # xlink subscribe/devices never returns productCode; treat any device
        # whose state has been populated by the device-state call as a mower.
        return self.state is not None


@dataclass
class CramerAuth:
    fleet_token: str
    guc_token: str
    guc_refresh_token: str
    organization_id: str
    guc_expires_in: int
    # Non-fleet (consumer) users use xlink for device access
    is_fleet_user: bool = True
    xlink_token: str = ""
    xlink_user_id: str = ""
    xlink_authorize: str = ""
    xlink_refresh_token: str = ""
    xlink_expires_in: int = XLINK_TOKEN_LIFETIME_S
    fetched_at: datetime = field(default_factory=datetime.now)

    @property
    def expires_in(self) -> int:
        """Seconds until the first of the tokens in use expires."""
        if self.xlink_token:
            return min(self.guc_expires_in, self.xlink_expires_in)
        return self.guc_expires_in

    @property
    def has_mqtt_credentials(self) -> bool:
        return bool(self.xlink_user_id and self.xlink_authorize)


class CramerConnectApiError(Exception):
    pass


class CramerConnectAuthError(CramerConnectApiError):
    """Login refused. `reason` is a config-flow error key (see LOGIN_ERROR_CODES)."""

    def __init__(self, message: str = "", reason: str = "invalid_auth") -> None:
        super().__init__(message)
        self.reason = reason


# Server error codes the app shows a specific message for (LoginActivity)
LOGIN_ERROR_CODES = {
    4001001: "invalid_auth",  # incorrect password
    4001007: "password_sync_required",  # changed on the Fleet Management website
    4001008: "not_activated",  # account e-mail not confirmed yet
    4001061: "too_many_attempts",
    4041011: "user_not_found",
}


def _error_details(text: str) -> tuple[int | None, str]:
    """Extract (code, message) from the error formats the Cramer servers use.

    xlink:  {"error": {"code": 4001001, "msg": "..."}}
    fleet:  {"title": "...", "status": 401, "traceId": "..."}
    GUC:    {"error_code": 1017, "error_message": "..."} or
            OAuth {"error": "invalid_grant", "error_description": "..."}
    """
    try:
        data = json.loads(text)
    except (TypeError, ValueError):
        return None, (text or "").strip()[:200]
    if not isinstance(data, dict):
        return None, ""
    err = data.get("error")
    if isinstance(err, dict):
        code = err.get("code") or err.get("error_code")
        msg = err.get("msg") or err.get("error_message") or ""
    else:
        code = data.get("error_code") or data.get("status")
        msg = (
            data.get("error_message") or data.get("error_description")
            or data.get("title") or (err if isinstance(err, str) else "") or ""
        )
    try:
        code = int(code) if code is not None else None
    except (TypeError, ValueError):
        code = None
    return code, str(msg)[:200]


async def _raise_for_login_error(resp: Any, step: str) -> None:
    """Turn a failed login response into a precise exception (never logs credentials)."""
    code, msg = _error_details(await resp.text())
    reason = LOGIN_ERROR_CODES.get(code) if code is not None else None
    if reason is not None or resp.status in (400, 401, 403):
        _LOGGER.warning(
            "%s login refused (HTTP %s, code %s): %s", step, resp.status, code, msg
        )
        raise CramerConnectAuthError(
            f"{step} login refused (HTTP {resp.status}, code {code})",
            reason=reason or "invalid_auth",
        )
    raise CramerConnectApiError(f"{step} login failed (HTTP {resp.status}, code {code}): {msg}")


class CramerConnectTokenExpiredError(CramerConnectAuthError):
    pass


def _base_headers() -> dict[str, str]:
    """Headers the app sends on every request."""
    return {
        "ApplicationKey": APP_APPLICATION_KEY,
        "Brand": APP_BRAND,
        "App-Name": APP_NAME,
        "Language": "en",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _parse_time(value: Any) -> datetime | None:
    """Parse an ISO 8601 timestamp such as '2026-11-05T04:33:05.273Z'."""
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _le16(value: int) -> str:
    """Little-endian uint16 hex, as StringUtils.getPin() in the app."""
    return (value & 0xFFFF).to_bytes(2, "little").hex()


def build_start_command(pin: str | int | None = None) -> str:
    """Start/resume mowing; the PIN is required when security level is 1/9."""
    if pin in (None, ""):
        return CMD_START
    return CMD_START_PREFIX + _le16(int(pin))


def build_park_command(minutes: int | None = None) -> str:
    """Park for `minutes` (None = until further notice)."""
    if minutes is None:
        return CMD_PARK_PREFIX + _le16(PARK_UNTIL_FURTHER_NOTICE)
    minutes = int(minutes)
    if not 1 <= minutes < PARK_UNTIL_FURTHER_NOTICE:
        raise ValueError(f"Park duration out of range: {minutes}")
    return CMD_PARK_PREFIX + _le16(minutes)


def build_stop_command(device: "CramerDevice") -> str:
    """Stop/pause; mowing the secondary area (state 12) has its own command."""
    if device.state == "12":
        return CMD_STOP_SECONDARY_AREA
    return CMD_STOP


class CramerConnectClient:
    def __init__(
        self,
        session: aiohttp.ClientSession,
        ssl_context: ssl.SSLContext | None = None,
    ) -> None:
        self._session = session
        self._ssl_context = ssl_context

    async def authenticate(self, username: str, password: str) -> CramerAuth:
        """Full login flow, branching on fleet vs. consumer account."""
        # The app trims both fields before logging in; a pasted e-mail with a
        # trailing space would otherwise be refused as invalid credentials.
        username = username.strip()
        password = password.strip()
        is_fleet = await self._is_fleet_user(username)

        if is_fleet:
            fleet_token, organization_id = await self._fleet_login(username, password)
            guc_token, guc_refresh, guc_expires = await self._get_guc_token(
                fleet_token, organization_id
            )
            auth = CramerAuth(
                fleet_token=fleet_token,
                guc_token=guc_token,
                guc_refresh_token=guc_refresh,
                organization_id=organization_id,
                guc_expires_in=guc_expires,
                is_fleet_user=True,
            )
            # The xlink token gives access to live datapoints and the MQTT
            # command channel. Not fatal if it fails — read-only still works.
            try:
                (
                    auth.xlink_token,
                    auth.xlink_user_id,
                    auth.xlink_authorize,
                ) = await self._get_fleet_xlink_token(fleet_token, organization_id)
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Fleet XlinkToken unavailable: %s", err)
            return auth
        else:
            (
                xlink_token, xlink_user_id, xlink_authorize, xlink_refresh, xlink_expires,
            ) = await self._xlink_login(username, password)
            # The xlink login proves the credentials are right. The GUC token is
            # only an extra header on xlink calls, so a GUC refusal must not be
            # reported as "invalid credentials".
            try:
                guc_token, guc_refresh, guc_expires = await self._guc_direct_login(
                    username, password
                )
            except CramerConnectAuthError as err:
                _LOGGER.warning(
                    "GUC login refused after a successful xlink login; "
                    "continuing without it (%s)", err,
                )
                guc_token, guc_refresh, guc_expires = "", "", xlink_expires
            return CramerAuth(
                fleet_token="",
                guc_token=guc_token,
                guc_refresh_token=guc_refresh,
                organization_id="",
                guc_expires_in=guc_expires,
                is_fleet_user=False,
                xlink_token=xlink_token,
                xlink_user_id=xlink_user_id,
                xlink_authorize=xlink_authorize,
                xlink_refresh_token=xlink_refresh,
                xlink_expires_in=xlink_expires,
            )

    async def refresh_guc_token(
        self, fleet_token: str, organization_id: str
    ) -> tuple[str, str, int]:
        """Re-fetch a GUC token using the fleet token (fleet users only)."""
        return await self._get_guc_token(fleet_token, organization_id)

    async def get_devices(self, auth: CramerAuth) -> list[CramerDevice]:
        if auth.is_fleet_user:
            return await self._get_devices_fleet(auth)
        return await self._get_devices_xlink(auth)

    async def get_device_status(
        self, auth: CramerAuth, product_id: str, device_id: str
    ) -> dict[str, Any]:
        url = (
            f"{FLEET_API_URL}/api/devices/{auth.organization_id}"
            f"/status/{product_id}/{device_id}"
        )
        headers = {**_base_headers(), "Authorization": f"Bearer {auth.fleet_token}"}
        async with self._session.get(url, headers=headers) as resp:
            if resp.status == 401:
                raise CramerConnectAuthError("Fleet token expired or invalid")
            if resp.status != 200:
                text = await resp.text()
                raise CramerConnectApiError(
                    f"Failed to get device status ({resp.status}): {text}"
                )
            return await resp.json()

    # ------------------------------------------------------------------
    # Fleet path
    # ------------------------------------------------------------------

    async def _is_fleet_user(self, username: str) -> bool:
        """Classify the account. Only a definite answer selects the consumer path.

        Network errors, timeouts, 429 and 5xx raise CramerConnectApiError so a
        temporary outage is not mistaken for "not a fleet user" (which would
        try a consumer login and end in a bogus re-authentication request).
        """
        url = f"{FLEET_AUTH_URL}/api/Authorization/user-exist"
        payload = {"username": username}
        try:
            async with self._session.post(url, json=payload, headers=_base_headers()) as resp:
                if resp.status == 429 or resp.status >= 500:
                    raise CramerConnectApiError(
                        f"Account classification unavailable (HTTP {resp.status})"
                    )
                if resp.status != 200:
                    _LOGGER.debug("user-exist returned %s, assuming non-fleet", resp.status)
                    return False
                data = await resp.json()
        except CramerConnectApiError:
            raise
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
            raise CramerConnectApiError(f"Account classification failed: {err}") from err
        if not isinstance(data, dict):
            raise CramerConnectApiError("Unexpected account classification response")
        return bool(data.get("existsOnFleet", False))

    async def _fleet_login(self, username: str, password: str) -> tuple[str, str]:
        """Returns (fleet_access_token, organization_id)."""
        url = f"{FLEET_API_URL}/api/Authenticate"
        payload = {"username": username, "password": password}
        async with self._session.post(url, json=payload, headers=_base_headers()) as resp:
            if resp.status != 200:
                await _raise_for_login_error(resp, "Fleet")
            data = await resp.json()

        token = data.get("access_token")
        if not token:
            raise CramerConnectAuthError("No access_token in fleet login response")

        org_id = data.get("owner_organization_id") or data.get("organization_id", "")
        return token, org_id

    async def _get_guc_token(
        self, fleet_token: str, organization_id: str
    ) -> tuple[str, str, int]:
        """Exchange fleet token for GUC token via fleet API."""
        url = f"{FLEET_API_URL}/api/account/GucToken"
        payload = {"organizationId": organization_id}
        headers = {**_base_headers(), "Authorization": f"Bearer {fleet_token}"}
        async with self._session.post(url, json=payload, headers=headers) as resp:
            if resp.status == 401:
                raise CramerConnectAuthError("Fleet token rejected by GucToken endpoint")
            if resp.status != 200:
                text = await resp.text()
                raise CramerConnectApiError(
                    f"GucToken request failed ({resp.status}): {text}"
                )
            data = await resp.json()

        token = data.get("accessToken")
        if not token:
            raise CramerConnectAuthError("No accessToken in GucToken response")

        refresh = data.get("refreshToken", "")
        expires_in = int(data.get("expireIn", 3600))
        return token, refresh, expires_in

    async def _get_fleet_xlink_token(
        self, fleet_token: str, organization_id: str
    ) -> tuple[str, str, str]:
        """Returns (xlink_token, xlink_user_id, authorize) for a fleet user."""
        url = f"{FLEET_API_URL}/api/account/XlinkToken"
        payload = {"organizationId": organization_id}
        headers = {**_base_headers(), "Authorization": f"Bearer {fleet_token}"}
        async with self._session.post(url, json=payload, headers=headers) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise CramerConnectApiError(
                    f"XlinkToken request failed ({resp.status}): {text}"
                )
            data = await resp.json()
        token = data.get("token") or ""
        user_id = str(data.get("xlinkId") or "")
        authorize = str(data.get("authString") or "")
        if not token or not user_id:
            raise CramerConnectApiError("Incomplete XlinkToken response")
        return token, user_id, authorize

    async def _get_devices_fleet(self, auth: CramerAuth) -> list[CramerDevice]:
        url = f"{FLEET_API_URL}/api/devices/{auth.organization_id}/subscribed"
        headers = {**_base_headers(), "Authorization": f"Bearer {auth.fleet_token}"}
        async with self._session.get(url, headers=headers) as resp:
            if resp.status == 401:
                raise CramerConnectAuthError("Fleet token expired or invalid")
            if resp.status != 200:
                text = await resp.text()
                raise CramerConnectApiError(
                    f"Failed to get devices ({resp.status}): {text}"
                )
            data: list[dict] = await resp.json()
        devices = self._parse_devices(data)
        if auth.xlink_token:
            await self._enrich_devices(auth, devices)
        return devices

    # ------------------------------------------------------------------
    # Consumer (non-fleet / xlink) path
    # ------------------------------------------------------------------

    async def _xlink_login(
        self, username: str, password: str
    ) -> tuple[str, str, str, str, int]:
        """Returns (access_token, user_id, authorize, refresh_token, expire_in)."""
        url = f"{XLINK_URL}/v2/user_auth"
        payload = {
            "corp_id": XLINK_CORP_ID,
            "email": username,
            "password": password,
            "resource": None,
            "phone": None,
            "phone_zone": None,
        }
        async with self._session.post(url, json=payload, headers=_base_headers()) as resp:
            if resp.status != 200:
                await _raise_for_login_error(resp, "Xlink")
            data = await resp.json()

        token = data.get("access_token")
        user_id = str(data.get("user_id", ""))
        authorize = str(data.get("authorize", ""))
        refresh = str(data.get("refresh_token", ""))
        if not token:
            raise CramerConnectAuthError("No access_token in xlink login response")
        try:
            expires = int(data.get("expire_in") or XLINK_TOKEN_LIFETIME_S)
        except (TypeError, ValueError):
            expires = XLINK_TOKEN_LIFETIME_S
        if expires <= 60:
            expires = XLINK_TOKEN_LIFETIME_S
        return token, user_id, authorize, refresh, expires

    async def _guc_direct_login(
        self, username: str, password: str
    ) -> tuple[str, str, int]:
        """Direct GUC password grant for consumer accounts."""
        url = f"{GUC_URL}/connect/token"
        form = {
            "scope": GUC_SCOPE,
            "grant_type": "password",
            "client_id": GUC_CLIENT_ID,
            "client_secret": GUC_CLIENT_SECRET,
            "username": username,
            "password": password,
            "HasLocationInfo": "true",  # the app always sends "true" with 0,0
            "Latitude": "0",
            "Longitude": "0",
            "LoginTime": str(int(time.time())),
        }
        headers = {
            "ApplicationKey": APP_APPLICATION_KEY,
            "Brand": APP_BRAND,
            "App-Name": APP_NAME,
            "Language": "en",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }
        try:
            async with self._session.post(url, data=form, headers=headers) as resp:
                if resp.status != 200:
                    await _raise_for_login_error(resp, "GUC")
                data = await resp.json()
        except CramerConnectApiError:
            raise
        except Exception as err:
            raise CramerConnectApiError(f"GUC direct login connection error: {err}") from err

        token = data.get("access_token")
        if not token:
            raise CramerConnectAuthError("No access_token in GUC direct login response")

        refresh = data.get("refresh_token", "")
        expires_in = int(data.get("expires_in", 3600))
        return token, refresh, expires_in

    async def _get_devices_xlink(self, auth: CramerAuth) -> list[CramerDevice]:
        url = f"{XLINK_URL}/v2/user/{auth.xlink_user_id}/subscribe/devices"
        headers = {
            **_base_headers(),
            **({"Authorization": f"Bearer {auth.guc_token}"} if auth.guc_token else {}),
            "Access-Token": auth.xlink_token,
            "Xlink-Access-Token": auth.xlink_token,
            "Xlink-User-Id": auth.xlink_user_id,
        }
        async with self._session.get(url, headers=headers) as resp:
            if resp.status == 401:
                raise CramerConnectAuthError("Xlink token expired or invalid")
            if resp.status != 200:
                text = await resp.text()
                raise CramerConnectApiError(
                    f"Failed to get xlink devices ({resp.status}): {text}"
                )
            data: list[dict] = await resp.json()

        devices = self._parse_devices(data)
        await self._enrich_devices(auth, devices)
        return devices

    async def _enrich_devices(
        self, auth: CramerAuth, devices: list[CramerDevice]
    ) -> None:
        """Enrich each device with live state + statistics (in place)."""
        enrichments = await asyncio.gather(
            *[self._get_xlink_device_state(auth, d) for d in devices],
            return_exceptions=True,
        )
        # An expired token affects every device: surface it so the
        # coordinator re-authenticates instead of showing stale data.
        for result in enrichments:
            if isinstance(result, CramerConnectAuthError):
                raise result
        for device, result in zip(devices, enrichments):
            if isinstance(result, Exception):
                _LOGGER.debug("Could not fetch state for %s: %s", device.name, result)
                continue
            if not isinstance(result, dict):
                continue
            for key in ("state", "battery", "next_start_ts",
                        "cutting_time_s", "running_time_s", "charging_time_s", "error_count",
                        "distance_m", "latitude", "longitude",
                        "software_version", "sw_update_available", "mower_model",
                        "source_for_next_start", "security_level",
                        "last_error_code", "last_error_time", "last_seen",
                        "wifi_signal", "lte_signal", "latest_software_version",
                        "schedule", "datapoints"):
                if result.get(key) is not None:
                    setattr(device, key, result[key])

    async def _get_xlink_device_state(
        self, auth: CramerAuth, device: CramerDevice
    ) -> dict[str, Any]:
        """Fetch live state + statistics from the xlink device-state endpoint.

        Returns a dict with keys: state, battery, next_start_ts,
        cutting_time_s, running_time_s, error_count.  Missing values are None.

        Datapoint 8  = security info (JSON string, 'response' object).
        Datapoint 32 = live mower state (JSON string, 'request' object).
        Datapoint 33 = last error event (JSON string, 'request' object).
        Datapoint 48 = usage statistics (JSON string, 'response' object).
        """
        product_id = device.product_id or device.raw.get("product_id", "")
        device_id = device.device_id
        url = f"{XLINK_URL}/v2/product/{product_id}/device-state/{device_id}"
        headers = {
            **_base_headers(),
            **({"Authorization": f"Bearer {auth.guc_token}"} if auth.guc_token else {}),
            "Access-Token": auth.xlink_token,
            "Xlink-Access-Token": auth.xlink_token,
            "Xlink-User-Id": auth.xlink_user_id,
        }
        async with self._session.get(url, headers=headers) as resp:
            if resp.status == 401:
                raise CramerConnectAuthError("Xlink token rejected by device-state")
            if resp.status != 200:
                return {}
            data = await resp.json()

        datapoints = data.get("datapoints") or {}
        result: dict[str, Any] = {"datapoints": datapoints} if datapoints else {}

        # --- dp[32]: live mower state ---
        dp32 = datapoints.get("32")
        if isinstance(dp32, dict) and isinstance(dp32.get("value"), str):
            try:
                req = json.loads(dp32["value"]).get("request") or {}
                if req.get("mower_main_state") is not None:
                    result["state"] = str(req["mower_main_state"])
                if req.get("battery_status") is not None:
                    result["battery"] = int(req["battery_status"])
                ns = req.get("next_start")
                if ns is not None:
                    next_start = int(ns)
                    # 0xFFFFFFFF (or -1 when signed) = "until further notice"
                    if next_start not in (0, -1, 0xFFFFFFFF):
                        result["next_start_ts"] = next_start
                if req.get("source_for_next_start") is not None:
                    result["source_for_next_start"] = int(req["source_for_next_start"])
            except (ValueError, TypeError, KeyError, AttributeError):
                pass
            last_seen = _parse_time(dp32.get("report_time"))
            if last_seen is not None:
                result["last_seen"] = last_seen

        # --- dp[31] / dp[36]: WiFi and mobile network signal quality (%) ---
        for dp_key, field_name, json_key in (
            ("31", "wifi_signal", "signal_quality"),
            ("36", "lte_signal", "gprs_lte_signal_quality"),
        ):
            dp = datapoints.get(dp_key)
            if isinstance(dp, dict) and isinstance(dp.get("value"), str):
                try:
                    resp_obj = json.loads(dp["value"]).get("response") or {}
                    if resp_obj.get(json_key) is not None:
                        result[field_name] = int(resp_obj[json_key])
                except (ValueError, TypeError, KeyError, AttributeError):
                    pass

        # --- dp[125]: weekly schedule ---
        dp125 = datapoints.get("125")
        if isinstance(dp125, dict) and isinstance(dp125.get("value"), str):
            try:
                resp_obj = json.loads(dp125["value"]).get("response") or {}
                if int(resp_obj.get("return_code", 0)) == 0:
                    schedule = parse_schedule(resp_obj)
                    if schedule is not None:
                        result["schedule"] = schedule
            except (ValueError, TypeError, AttributeError):
                pass

        # --- dp[119]: header of the firmware offered to the mower ---
        # bytes 0-4 "#RLM@", 5 pad, 6 major, 7 minor, 8-11 build (LE)
        dp119 = datapoints.get("119")
        if isinstance(dp119, dict) and isinstance(dp119.get("value"), str):
            try:
                resp_obj = json.loads(dp119["value"]).get("response") or {}
                header = bytes.fromhex(resp_obj.get("program_header") or "")
                if len(header) >= 12 and header[:4] == b"#RLM":
                    build = int.from_bytes(header[8:12], "little")
                    result["latest_software_version"] = f"{header[6]}.{header[7]}.{build}"
            except (ValueError, TypeError, KeyError, AttributeError):
                pass

        # --- dp[8]: security level (PIN required for commands when 1 or 9) ---
        dp8 = datapoints.get("8")
        if isinstance(dp8, dict) and isinstance(dp8.get("value"), str):
            try:
                resp_obj = json.loads(dp8["value"]).get("response") or {}
                if (
                    int(resp_obj.get("return_code", -1)) == 0
                    and resp_obj.get("security_level") is not None
                ):
                    result["security_level"] = int(resp_obj["security_level"])
            except (ValueError, TypeError, KeyError, AttributeError):
                pass

        # --- dp[33]: last error event ---
        dp33 = datapoints.get("33")
        if isinstance(dp33, dict) and isinstance(dp33.get("value"), str):
            try:
                req = json.loads(dp33["value"]).get("request") or {}
                if req.get("event_id") is not None:
                    result["last_error_code"] = int(req["event_id"])
                    result["last_error_time"] = req.get("request_time") or dp33.get(
                        "report_time"
                    )
            except (ValueError, TypeError, KeyError, AttributeError):
                pass

        # --- dp[34]: current GPS position ---
        dp34 = datapoints.get("34")
        if isinstance(dp34, dict) and isinstance(dp34.get("value"), str):
            try:
                req = json.loads(dp34["value"]).get("request") or {}
                if req.get("latitude") is not None:
                    result["latitude"] = float(req["latitude"])
                if req.get("longitude") is not None:
                    result["longitude"] = float(req["longitude"])
            except (ValueError, TypeError, KeyError):
                pass

        # --- dp[48]: usage statistics ---
        dp48 = datapoints.get("48")
        if isinstance(dp48, dict) and isinstance(dp48.get("value"), str):
            try:
                resp_obj = json.loads(dp48["value"]).get("response") or {}
                if resp_obj.get("cutting_time") is not None:
                    result["cutting_time_s"] = int(resp_obj["cutting_time"])
                if resp_obj.get("running_time") is not None:
                    result["running_time_s"] = int(resp_obj["running_time"])
                if resp_obj.get("charging_time") is not None:
                    result["charging_time_s"] = int(resp_obj["charging_time"])
                if resp_obj.get("no_of_fatal_error") is not None:
                    result["error_count"] = int(resp_obj["no_of_fatal_error"])
            except (ValueError, TypeError, KeyError):
                pass

        # --- dp[117]: software versions + update flag ---
        dp117 = datapoints.get("117")
        if isinstance(dp117, dict) and isinstance(dp117.get("value"), str):
            try:
                parsed = json.loads(dp117["value"])
                req = parsed.get("request") or {}
                major = req.get("mower_main_application_major_sw_version")
                minor = req.get("mower_main_application_minor_sw_version")
                build = req.get("mower_main_application_build_no")
                if None not in (major, minor, build):
                    result["software_version"] = f"{int(major)}.{int(minor)}.{int(build)}"
                resp_obj = parsed.get("response") or {}
                if resp_obj.get("sw_update") is not None:
                    result["sw_update_available"] = bool(resp_obj["sw_update"])
            except (ValueError, TypeError, KeyError):
                pass

        # --- dp[21]: hardware model name ---
        dp21 = datapoints.get("21")
        if isinstance(dp21, dict) and isinstance(dp21.get("value"), str):
            try:
                resp_obj = json.loads(dp21["value"]).get("response") or {}
                raw_name = resp_obj.get("mower_name", "")
                clean_name = raw_name.split("\x00")[0].strip()
                if clean_name:
                    result["mower_model"] = clean_name
            except (ValueError, TypeError, KeyError):
                pass

        # --- dp[225]: total mowing distance (hex metres) ---
        dp225 = datapoints.get("225")
        if isinstance(dp225, dict) and isinstance(dp225.get("value"), str):
            try:
                result["distance_m"] = int(dp225["value"].strip(), 16)
            except (ValueError, TypeError):
                pass

        # --- dp[246]: software version string (fallback when dp[117] is absent) ---
        dp246 = datapoints.get("246")
        if (
            "software_version" not in result
            and isinstance(dp246, dict)
            and isinstance(dp246.get("value"), str)
        ):
            val = dp246["value"].strip()
            if val:
                result["software_version"] = val

        return result

    async def send_command(
        self,
        auth: CramerAuth,
        device_id: str,
        payload_hex: str,
    ) -> None:
        """Publish a command to an RLM1 mower over MQTT, exactly like the app.

        Broker: ssl://mqtt.globetools.systems:1884 (MQTT 3.1.1)
        Username: xlink user id; password: md5(user_id + authorize)
        Topic: "$7/<device_id>"; payload: raw bytes of the hex command string.
        """
        if not auth.has_mqtt_credentials:
            raise CramerConnectApiError(
                "No MQTT credentials available for this account"
            )
        if self._ssl_context is None:
            self._ssl_context = await asyncio.get_running_loop().run_in_executor(
                None, ssl.create_default_context
            )
        password = hashlib.md5(
            (auth.xlink_user_id + auth.xlink_authorize).encode()
        ).hexdigest()
        client_id = f"X:APP;A:4;V:1;RES:{secrets.token_hex(8)};"
        topic = MQTT_COMMAND_TOPIC.format(device_id=device_id)
        try:
            payload = bytes.fromhex(payload_hex)
        except ValueError as err:
            raise CramerConnectApiError(f"Invalid command payload: {err}") from err

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(
                    MQTT_HOST,
                    MQTT_PORT,
                    ssl=self._ssl_context,
                    server_hostname=MQTT_HOST,
                ),
                timeout=10,
            )
        except (OSError, asyncio.TimeoutError) as err:
            raise CramerConnectApiError(f"MQTT connection failed: {err}") from err

        try:
            await asyncio.wait_for(
                _mqtt_publish(
                    reader, writer, client_id, auth.xlink_user_id, password,
                    topic, payload,
                ),
                timeout=15,
            )
            _LOGGER.debug("MQTT published %s to %s", payload_hex, topic)
        except asyncio.TimeoutError as err:
            raise CramerConnectApiError("MQTT command timed out") from err
        except (OSError, asyncio.IncompleteReadError) as err:
            raise CramerConnectApiError(f"MQTT error: {err}") from err
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:  # noqa: BLE001
                pass

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_devices(data: list[dict]) -> list[CramerDevice]:
        devices = []
        for item in data or []:
            product_model = item.get("productModel") or {}
            product_code = item.get("productCode") or product_model.get("productCode", "")

            # xlink returns state/battery nested in deviceStateBean;
            # fleet API returns them at the top level
            dsb = item.get("deviceStateBean") or {}
            raw_state = item.get("state")
            if raw_state is None:
                raw_state = dsb.get("mower_main_state") if dsb.get("mower_main_state") is not None else dsb.get("current_mower_main_state")
            battery = item.get("battery")
            if battery is None:
                battery = dsb.get("battery_status")

            devices.append(
                CramerDevice(
                    device_id=str(item.get("id", "")),
                    product_id=str(item.get("product_id", "")),
                    name=item.get("name") or item.get("batteryPropertyName") or "Cramer Mower",
                    serial_number=item.get("sn", ""),
                    mac=item.get("mac", ""),
                    product_code=product_code,
                    state=str(raw_state) if raw_state is not None else None,
                    battery=battery,
                    is_online=bool(item.get("is_online", False)),
                    device_authorize=str(item.get("authorize_code", "")),
                    raw=item,
                )
            )
        return devices


# ----------------------------------------------------------------------
# Minimal MQTT 3.1.1 client (CONNECT → PUBLISH QoS 1 → DISCONNECT)
# ----------------------------------------------------------------------

_MQTT_CONNACK_ERRORS = {
    1: "unacceptable protocol version",
    2: "client identifier rejected",
    3: "server unavailable",
    4: "bad username or password",
    5: "not authorized",
}


def _mqtt_str(value: str | bytes) -> bytes:
    data = value.encode() if isinstance(value, str) else value
    return len(data).to_bytes(2, "big") + data


def _mqtt_packet(header: int, body: bytes) -> bytes:
    length = len(body)
    encoded = bytearray()
    while True:
        byte = length % 128
        length //= 128
        if length:
            byte |= 0x80
        encoded.append(byte)
        if not length:
            break
    return bytes([header]) + bytes(encoded) + body


async def _mqtt_read_packet(reader: asyncio.StreamReader) -> tuple[int, bytes]:
    header = (await reader.readexactly(1))[0]
    multiplier, length = 1, 0
    for _ in range(4):
        byte = (await reader.readexactly(1))[0]
        length += (byte & 0x7F) * multiplier
        if not byte & 0x80:
            break
        multiplier *= 128
    body = await reader.readexactly(length) if length else b""
    return header, body


async def _mqtt_publish(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    client_id: str,
    username: str,
    password: str,
    topic: str,
    payload: bytes,
) -> None:
    # CONNECT: protocol "MQTT" level 4, flags user+password+clean session
    connect = (
        _mqtt_str("MQTT") + bytes([0x04, 0xC2]) + (60).to_bytes(2, "big")
        + _mqtt_str(client_id) + _mqtt_str(username) + _mqtt_str(password)
    )
    writer.write(_mqtt_packet(0x10, connect))
    await writer.drain()

    header, body = await _mqtt_read_packet(reader)
    if header >> 4 != 2 or len(body) < 2:
        raise CramerConnectApiError(f"Unexpected MQTT reply 0x{header:02x}")
    if body[1] != 0:
        reason = _MQTT_CONNACK_ERRORS.get(body[1], f"code {body[1]}")
        if body[1] in (4, 5):
            raise CramerConnectTokenExpiredError(f"MQTT login refused: {reason}")
        raise CramerConnectApiError(f"MQTT connection refused: {reason}")

    packet_id = 1
    publish = _mqtt_str(topic) + packet_id.to_bytes(2, "big") + payload
    writer.write(_mqtt_packet(0x32, publish))  # PUBLISH, QoS 1
    await writer.drain()

    while True:
        header, body = await _mqtt_read_packet(reader)
        if header >> 4 == 4 and body[:2] == packet_id.to_bytes(2, "big"):
            break  # PUBACK

    writer.write(b"\xe0\x00")  # DISCONNECT
    await writer.drain()
