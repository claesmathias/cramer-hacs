"""Cramer Connect API client."""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import aiohttp

from .const import (
    APP_APPLICATION_KEY,
    APP_BRAND,
    APP_NAME,
    FLEET_API_URL,
    FLEET_AUTH_URL,
    GUC_CLIENT_ID,
    GUC_CLIENT_SECRET,
    GUC_SCOPE,
    GUC_URL,
    MOWER_STATE_MAP,
    ROBOTIC_MOWER_PRODUCT_CODES,
    XLINK_CORP_ID,
    XLINK_URL,
)

_LOGGER = logging.getLogger(__name__)


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
    error_count: int | None = None
    distance_m: int | None = None
    # GPS from dp[32]
    latitude: float | None = None
    longitude: float | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def state_label(self) -> str:
        return MOWER_STATE_MAP.get(self.state or "", "unknown")

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
    fetched_at: datetime = field(default_factory=datetime.now)


class CramerConnectApiError(Exception):
    pass


class CramerConnectAuthError(CramerConnectApiError):
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


class CramerConnectClient:
    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    async def authenticate(self, username: str, password: str) -> CramerAuth:
        """Full login flow, branching on fleet vs. consumer account."""
        is_fleet = await self._is_fleet_user(username)

        if is_fleet:
            fleet_token, organization_id = await self._fleet_login(username, password)
            guc_token, guc_refresh, guc_expires = await self._get_guc_token(
                fleet_token, organization_id
            )
            return CramerAuth(
                fleet_token=fleet_token,
                guc_token=guc_token,
                guc_refresh_token=guc_refresh,
                organization_id=organization_id,
                guc_expires_in=guc_expires,
                is_fleet_user=True,
            )
        else:
            xlink_token, xlink_user_id = await self._xlink_login(username, password)
            guc_token, guc_refresh, guc_expires = await self._guc_direct_login(
                username, password
            )
            return CramerAuth(
                fleet_token="",
                guc_token=guc_token,
                guc_refresh_token=guc_refresh,
                organization_id="",
                guc_expires_in=guc_expires,
                is_fleet_user=False,
                xlink_token=xlink_token,
                xlink_user_id=xlink_user_id,
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
        url = f"{FLEET_AUTH_URL}/api/Authorization/user-exist"
        payload = {"username": username}
        try:
            async with self._session.post(url, json=payload, headers=_base_headers()) as resp:
                if resp.status != 200:
                    _LOGGER.debug("user-exist returned %s, assuming non-fleet", resp.status)
                    return False
                data = await resp.json()
        except Exception as err:
            _LOGGER.debug("user-exist failed (%s), assuming non-fleet", err)
            return False
        return bool(data.get("existsOnFleet", False))

    async def _fleet_login(self, username: str, password: str) -> tuple[str, str]:
        """Returns (fleet_access_token, organization_id)."""
        url = f"{FLEET_API_URL}/api/Authenticate"
        payload = {"username": username, "password": password}
        async with self._session.post(url, json=payload, headers=_base_headers()) as resp:
            if resp.status in (400, 401, 403):
                text = await resp.text()
                _LOGGER.debug("Fleet login %s: %s", resp.status, text)
                raise CramerConnectAuthError("Invalid credentials")
            if resp.status != 200:
                text = await resp.text()
                raise CramerConnectApiError(
                    f"Fleet login failed ({resp.status}): {text}"
                )
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
        return self._parse_devices(data)

    # ------------------------------------------------------------------
    # Consumer (non-fleet / xlink) path
    # ------------------------------------------------------------------

    async def _xlink_login(self, username: str, password: str) -> tuple[str, str]:
        """Returns (xlink_access_token, xlink_user_id)."""
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
            if resp.status in (400, 401, 403):
                text = await resp.text()
                _LOGGER.debug("Xlink login %s: %s", resp.status, text)
                raise CramerConnectAuthError("Invalid credentials")
            if resp.status != 200:
                text = await resp.text()
                raise CramerConnectApiError(
                    f"Xlink login failed ({resp.status}): {text}"
                )
            data = await resp.json()

        token = data.get("access_token")
        user_id = str(data.get("user_id", ""))
        if not token:
            raise CramerConnectAuthError("No access_token in xlink login response")
        return token, user_id

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
            "HasLocationInfo": "false",
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
                if resp.status in (400, 401, 403):
                    text = await resp.text()
                    _LOGGER.debug("GUC direct login %s: %s", resp.status, text)
                    raise CramerConnectAuthError("Invalid credentials (GUC)")
                if resp.status != 200:
                    text = await resp.text()
                    raise CramerConnectApiError(
                        f"GUC direct login failed ({resp.status}): {text}"
                    )
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

        # Enrich each device with live state + statistics
        enrichments = await asyncio.gather(
            *[self._get_xlink_device_state(auth, d) for d in devices],
            return_exceptions=True,
        )
        for device, result in zip(devices, enrichments):
            if isinstance(result, Exception):
                _LOGGER.debug("Could not fetch state for %s: %s", device.name, result)
                continue
            if not isinstance(result, dict):
                continue
            for key in ("state", "battery", "next_start_ts",
                        "cutting_time_s", "running_time_s", "error_count",
                        "distance_m", "latitude", "longitude"):
                if result.get(key) is not None:
                    setattr(device, key, result[key])

        return devices

    async def _get_xlink_device_state(
        self, auth: CramerAuth, device: CramerDevice
    ) -> dict[str, Any]:
        """Fetch live state + statistics from the xlink device-state endpoint.

        Returns a dict with keys: state, battery, next_start_ts,
        cutting_time_s, running_time_s, error_count.  Missing values are None.

        Datapoint 32 = live mower state (JSON string, 'request' object).
        Datapoint 48 = usage statistics (JSON string, 'response' object).
        """
        import json as _json

        product_id = device.product_id or device.raw.get("product_id", "")
        device_id = device.device_id
        url = f"{XLINK_URL}/v2/product/{product_id}/device-state/{device_id}"
        headers = {
            **_base_headers(),
            "Access-Token": auth.xlink_token,
            "Xlink-Access-Token": auth.xlink_token,
            "Xlink-User-Id": auth.xlink_user_id,
        }
        async with self._session.get(url, headers=headers) as resp:
            if resp.status != 200:
                return {}
            data = await resp.json()

        datapoints = data.get("datapoints") or {}
        result: dict[str, Any] = {}

        # --- dp[32]: live mower state + GPS ---
        dp32 = datapoints.get("32")
        if isinstance(dp32, dict) and isinstance(dp32.get("value"), str):
            try:
                req = _json.loads(dp32["value"]).get("request") or {}
                if req.get("mower_main_state") is not None:
                    result["state"] = str(req["mower_main_state"])
                if req.get("battery_status") is not None:
                    result["battery"] = int(req["battery_status"])
                ns = req.get("next_start")
                if ns is not None and int(ns) != 0xFFFFFFFF:
                    result["next_start_ts"] = int(ns)
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
                resp_obj = _json.loads(dp48["value"]).get("response") or {}
                if resp_obj.get("cutting_time") is not None:
                    result["cutting_time_s"] = int(resp_obj["cutting_time"])
                if resp_obj.get("running_time") is not None:
                    result["running_time_s"] = int(resp_obj["running_time"])
                if resp_obj.get("no_of_fatal_error") is not None:
                    result["error_count"] = int(resp_obj["no_of_fatal_error"])
                if resp_obj.get("cutting_distance") is not None:
                    result["distance_m"] = int(resp_obj["cutting_distance"])
            except (ValueError, TypeError, KeyError):
                pass

        return result

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
                    raw=item,
                )
            )
        return devices
