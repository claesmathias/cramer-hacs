"""Unit tests for the Cramer Connect API client."""
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

# conftest.py installs all homeassistant stubs before this module is loaded.
from custom_components.cramer_connect.api import (  # noqa: E402
    CramerAuth,
    CramerConnectApiError,
    CramerConnectAuthError,
    CramerConnectClient,
    CramerDevice,
)

# ---------------------------------------------------------------------------
# Shared fixtures / test data
# ---------------------------------------------------------------------------

IS_FLEET_TRUE = {"existsOnFleet": True}
IS_FLEET_FALSE = {"existsOnFleet": False}

FLEET_LOGIN_OK = {
    "access_token": "fleet-token-abc",
    "organization_id": "org-123",
    "owner_organization_id": "",
    "expiration": "2026-05-26T00:00:00Z",
    "user_name": "test@example.com",
    "is_admin": False,
}

GUC_TOKEN_OK = {
    "accessToken": "guc-token-xyz",
    "refreshToken": "guc-refresh-xyz",
    "expireIn": 3600,
    "tokenType": "Bearer",
}

XLINK_LOGIN_OK = {
    "access_token": "xlink-token-abc",
    "user_id": "user-123",
    "refresh_token": "xlink-refresh-abc",
    "expire_in": 7200,
    "authorize": "auth-string",
}

GUC_DIRECT_OK = {
    "access_token": "guc-direct-token-xyz",
    "refresh_token": "guc-direct-refresh-xyz",
    "expires_in": 3600,
    "token_type": "Bearer",
}

import json as _json

DP32_VALUE = _json.dumps({
    "request": {
        "mower_main_state": 4,
        "battery_status": 78,
        "next_start": 1800000000,
        "source_for_next_start": 2,
    },
    "response": {"return_code": 0},
})

DP34_VALUE = _json.dumps({
    "request": {
        "latitude": "52.0000",
        "longitude": "5.0000",
        "hdop": "1.0",
        "request_time": "2026-01-01T12:00:00Z",
    },
    "response": {"return_code": 0},
})

DP48_VALUE = _json.dumps({
    "request": {"request_time": "2026-01-01T00:00:00Z"},
    "response": {
        "return_code": 0,
        "cutting_time": 3600,
        "running_time": 7200,
        "charging_time": 1800,
        "no_of_fatal_error": 5,
    },
})

DP117_VALUE = _json.dumps({
    "request": {
        "mower_main_application_major_sw_version": 13,
        "mower_main_application_minor_sw_version": 5,
        "mower_main_application_build_no": 100000000,
    },
    "response": {"return_code": 0, "sw_update": 1},
})

DP21_VALUE = _json.dumps({
    "request": {},
    "response": {
        "return_code": 0,
        "mower_name": "Test RM1000\x00\xff\xff",
        "serial_number": 100000001,
    },
})

DEVICE_STATE_OK = {
    "datapoints": {
        "21": {"report_time": "2026-01-01T00:00:00Z", "value": DP21_VALUE},
        "32": {"report_time": "2026-05-26T12:00:00Z", "value": DP32_VALUE},
        "34": {"report_time": "2026-05-26T12:00:00Z", "value": DP34_VALUE},
        "48": {"report_time": "2026-03-01T00:00:00Z", "value": DP48_VALUE},
        "117": {"report_time": "2026-05-26T12:00:00Z", "value": DP117_VALUE},
        "225": {"report_time": "2026-05-26T12:00:00Z", "value": "00002710"},  # 10000 m
        "246": {"report_time": "2026-05-26T12:00:00Z", "value": "13.5.100000000"},
    }
}

DEVICE_LIST_OK = [
    {
        "id": 12345,
        "product_id": "prod-001",
        "name": "My Mower",
        "sn": "SN-FLEET-001",
        "mac": "AA:BB:CC:DD:EE:FF",
        "productCode": "RLM1",
        "state": 4,
        "battery": 78,
        "is_online": True,
    }
]

# xlink subscribe/devices returns no productCode, state, or battery
XLINK_DEVICE_LIST_OK = [
    {
        "id": 100000001,
        "product_id": "aabbccddeeff00112233445566778899",
        "name": "Test Mower",
        "sn": "SN-XLINK-001",
        "mac": "aabbccddeeff",
        "is_online": True,
    }
]


def _make_response(status: int, body: dict | list) -> MagicMock:
    resp = MagicMock()
    resp.status = status
    resp.json = AsyncMock(return_value=body)
    resp.text = AsyncMock(return_value=json.dumps(body))
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=False)
    return resp


def _auth(**kwargs) -> CramerAuth:
    defaults = dict(
        fleet_token="fleet-tok",
        guc_token="guc-tok",
        guc_refresh_token="refresh",
        organization_id="org-123",
        guc_expires_in=3600,
        is_fleet_user=True,
    )
    return CramerAuth(**{**defaults, **kwargs})


def _client_with_posts(*responses) -> CramerConnectClient:
    session = MagicMock()
    session.post = MagicMock(side_effect=list(responses))
    return CramerConnectClient(session)


def _client_with_get(response) -> CramerConnectClient:
    session = MagicMock()
    session.get = MagicMock(return_value=response)
    return CramerConnectClient(session)


def _client_with_gets(*responses) -> CramerConnectClient:
    """Client whose session.get returns successive responses."""
    session = MagicMock()
    session.get = MagicMock(side_effect=list(responses))
    return CramerConnectClient(session)


# ---------------------------------------------------------------------------
# authenticate() — fleet path
# ---------------------------------------------------------------------------

class TestAuthenticateFleet:
    async def test_success(self):
        # Posts: 1) user-exist, 2) fleet login, 3) GUC token
        client = _client_with_posts(
            _make_response(200, IS_FLEET_TRUE),
            _make_response(200, FLEET_LOGIN_OK),
            _make_response(200, GUC_TOKEN_OK),
        )
        auth = await client.authenticate("test@example.com", "secret")

        assert auth.fleet_token == "fleet-token-abc"
        assert auth.guc_token == "guc-token-xyz"
        assert auth.guc_refresh_token == "guc-refresh-xyz"
        assert auth.organization_id == "org-123"
        assert auth.guc_expires_in == 3600
        assert auth.is_fleet_user is True

    async def test_invalid_credentials_401(self):
        client = _client_with_posts(
            _make_response(200, IS_FLEET_TRUE),
            _make_response(401, {"error": "Unauthorized"}),
        )
        with pytest.raises(CramerConnectAuthError):
            await client.authenticate("bad@example.com", "wrong")

    async def test_invalid_credentials_400(self):
        client = _client_with_posts(
            _make_response(200, IS_FLEET_TRUE),
            _make_response(400, {"error": "Bad Request"}),
        )
        with pytest.raises(CramerConnectAuthError):
            await client.authenticate("bad@example.com", "wrong")

    async def test_fleet_server_error_raises_api_error(self):
        client = _client_with_posts(
            _make_response(200, IS_FLEET_TRUE),
            _make_response(500, {"error": "Internal Server Error"}),
        )
        with pytest.raises(CramerConnectApiError):
            await client.authenticate("test@example.com", "secret")

    async def test_missing_access_token_raises_auth_error(self):
        client = _client_with_posts(
            _make_response(200, IS_FLEET_TRUE),
            _make_response(200, {"organization_id": "org-123"}),
        )
        with pytest.raises(CramerConnectAuthError, match="No access_token"):
            await client.authenticate("test@example.com", "secret")

    async def test_owner_organization_id_preferred(self):
        body = {**FLEET_LOGIN_OK, "owner_organization_id": "owner-org-999"}
        client = _client_with_posts(
            _make_response(200, IS_FLEET_TRUE),
            _make_response(200, body),
            _make_response(200, GUC_TOKEN_OK),
        )
        auth = await client.authenticate("test@example.com", "secret")
        assert auth.organization_id == "owner-org-999"

    async def test_guc_token_exchange_server_error(self):
        client = _client_with_posts(
            _make_response(200, IS_FLEET_TRUE),
            _make_response(200, FLEET_LOGIN_OK),
            _make_response(500, {"error": "GUC error"}),
        )
        with pytest.raises(CramerConnectApiError):
            await client.authenticate("test@example.com", "secret")

    async def test_guc_missing_access_token_raises_auth_error(self):
        client = _client_with_posts(
            _make_response(200, IS_FLEET_TRUE),
            _make_response(200, FLEET_LOGIN_OK),
            _make_response(200, {"refreshToken": "r", "expireIn": 3600}),
        )
        with pytest.raises(CramerConnectAuthError, match="No accessToken"):
            await client.authenticate("test@example.com", "secret")

    async def test_guc_401_raises_auth_error(self):
        client = _client_with_posts(
            _make_response(200, IS_FLEET_TRUE),
            _make_response(200, FLEET_LOGIN_OK),
            _make_response(401, {}),
        )
        with pytest.raises(CramerConnectAuthError):
            await client.authenticate("test@example.com", "secret")

    async def test_correct_headers_sent(self):
        """ApplicationKey, Brand and App-Name must be present in every request."""
        session = MagicMock()
        session.post = MagicMock(side_effect=[
            _make_response(200, IS_FLEET_TRUE),
            _make_response(200, FLEET_LOGIN_OK),
            _make_response(200, GUC_TOKEN_OK),
        ])
        client = CramerConnectClient(session)
        await client.authenticate("test@example.com", "secret")

        # Second call is the fleet login (index 1)
        _, kwargs = session.post.call_args_list[1]
        headers = kwargs.get("headers", {})
        assert "ApplicationKey" in headers
        assert headers.get("Brand") == "Cramer"
        assert "App-Name" in headers


# ---------------------------------------------------------------------------
# authenticate() — consumer (xlink) path
# ---------------------------------------------------------------------------

class TestAuthenticateConsumer:
    async def test_success(self):
        # Posts: 1) user-exist (false), 2) xlink login, 3) GUC direct login
        client = _client_with_posts(
            _make_response(200, IS_FLEET_FALSE),
            _make_response(200, XLINK_LOGIN_OK),
            _make_response(200, GUC_DIRECT_OK),
        )
        auth = await client.authenticate("consumer@example.com", "secret")

        assert auth.is_fleet_user is False
        assert auth.xlink_token == "xlink-token-abc"
        assert auth.xlink_user_id == "user-123"
        assert auth.xlink_authorize == "auth-string"
        assert auth.guc_token == "guc-direct-token-xyz"
        assert auth.guc_refresh_token == "guc-direct-refresh-xyz"
        assert auth.guc_expires_in == 3600
        assert auth.fleet_token == ""
        assert auth.organization_id == ""

    async def test_xlink_invalid_credentials_401(self):
        client = _client_with_posts(
            _make_response(200, IS_FLEET_FALSE),
            _make_response(401, {"error": "Unauthorized"}),
        )
        with pytest.raises(CramerConnectAuthError):
            await client.authenticate("bad@example.com", "wrong")

    async def test_xlink_server_error_raises_api_error(self):
        client = _client_with_posts(
            _make_response(200, IS_FLEET_FALSE),
            _make_response(500, {}),
        )
        with pytest.raises(CramerConnectApiError):
            await client.authenticate("consumer@example.com", "secret")

    async def test_guc_direct_invalid_credentials(self):
        client = _client_with_posts(
            _make_response(200, IS_FLEET_FALSE),
            _make_response(200, XLINK_LOGIN_OK),
            _make_response(401, {}),
        )
        with pytest.raises(CramerConnectAuthError):
            await client.authenticate("consumer@example.com", "wrong")

    async def test_user_exist_4xx_falls_back_to_consumer(self):
        """A definite 4xx from user-exist selects the consumer path."""
        client = _client_with_posts(
            _make_response(404, {}),
            _make_response(200, XLINK_LOGIN_OK),
            _make_response(200, GUC_DIRECT_OK),
        )
        auth = await client.authenticate("consumer@example.com", "secret")
        assert auth.is_fleet_user is False

    @pytest.mark.parametrize("status", [429, 500, 502, 503])
    async def test_user_exist_outage_raises_api_error(self, status):
        """A server outage must not be mistaken for a consumer account."""
        client = _client_with_posts(_make_response(status, {}))
        with pytest.raises(CramerConnectApiError) as exc:
            await client.authenticate("fleet@example.com", "secret")
        assert not isinstance(exc.value, CramerConnectAuthError)
        assert client._session.post.call_count == 1  # no consumer login attempted

    async def test_user_exist_network_error_raises_api_error(self):
        import aiohttp
        session = MagicMock()
        session.post = MagicMock(side_effect=aiohttp.ClientConnectionError("down"))
        with pytest.raises(CramerConnectApiError) as exc:
            await CramerConnectClient(session).authenticate("a@b.c", "pw")
        assert not isinstance(exc.value, CramerConnectAuthError)

    async def test_user_exist_malformed_json_raises_api_error(self):
        resp = _make_response(200, {})
        resp.json = AsyncMock(side_effect=ValueError("not json"))
        client = _client_with_posts(resp)
        with pytest.raises(CramerConnectApiError):
            await client.authenticate("a@b.c", "pw")

    async def test_xlink_expiry_taken_from_login_response(self):
        client = _client_with_posts(
            _make_response(200, IS_FLEET_FALSE),
            _make_response(200, {**XLINK_LOGIN_OK, "expire_in": 3000}),
            _make_response(200, {**GUC_DIRECT_OK, "expires_in": 86400}),
        )
        auth = await client.authenticate("consumer@example.com", "secret")
        assert auth.xlink_expires_in == 3000
        assert auth.expires_in == 3000

    async def test_missing_xlink_expiry_defaults_to_two_hours(self):
        body = {k: v for k, v in XLINK_LOGIN_OK.items() if k != "expire_in"}
        client = _client_with_posts(
            _make_response(200, IS_FLEET_FALSE),
            _make_response(200, body),
            _make_response(200, GUC_DIRECT_OK),
        )
        auth = await client.authenticate("consumer@example.com", "secret")
        assert auth.xlink_expires_in == 7200


# ---------------------------------------------------------------------------
# get_devices()
# ---------------------------------------------------------------------------

class TestGetDevices:
    async def test_returns_mower_device(self):
        client = _client_with_get(_make_response(200, DEVICE_LIST_OK))
        devices = await client.get_devices(_auth())

        assert len(devices) == 1
        d = devices[0]
        assert d.device_id == "12345"
        assert d.name == "My Mower"
        assert d.product_code == "RLM1"
        assert d.state == "4"
        assert d.state_label == "mowing"
        assert d.battery == 78
        assert d.is_online is True
        assert d.is_mower is True

    async def test_401_raises_auth_error(self):
        client = _client_with_get(_make_response(401, {}))
        with pytest.raises(CramerConnectAuthError):
            await client.get_devices(_auth())

    async def test_500_raises_api_error(self):
        client = _client_with_get(_make_response(500, {}))
        with pytest.raises(CramerConnectApiError):
            await client.get_devices(_auth())

    async def test_empty_list(self):
        client = _client_with_get(_make_response(200, []))
        assert await client.get_devices(_auth()) == []

    async def test_non_mower_device_flagged_correctly(self):
        body = [{**DEVICE_LIST_OK[0], "productCode": "BATTERY"}]
        client = _client_with_get(_make_response(200, body))
        devices = await client.get_devices(_auth())
        assert devices[0].is_mower is False

    async def test_fleet_token_used_in_authorization_header(self):
        session = MagicMock()
        session.get = MagicMock(return_value=_make_response(200, DEVICE_LIST_OK))
        client = CramerConnectClient(session)
        await client.get_devices(_auth(fleet_token="my-fleet-token"))

        _, kwargs = session.get.call_args
        assert kwargs["headers"]["Authorization"] == "Bearer my-fleet-token"

    async def test_xlink_devices_use_access_token_header(self):
        session = MagicMock()
        session.get = MagicMock(return_value=_make_response(200, DEVICE_LIST_OK))
        client = CramerConnectClient(session)
        consumer_auth = _auth(
            is_fleet_user=False,
            fleet_token="",
            organization_id="",
            guc_token="my-guc-token",
            xlink_token="my-xlink-token",
            xlink_user_id="u-99",
        )
        await client.get_devices(consumer_auth)

        _, kwargs = session.get.call_args
        assert kwargs["headers"]["Access-Token"] == "my-xlink-token"
        assert kwargs["headers"]["Authorization"] == "Bearer my-guc-token"
        assert kwargs["headers"]["Xlink-User-Id"] == "u-99"

    async def test_xlink_401_raises_auth_error(self):
        client = _client_with_get(_make_response(401, {}))
        consumer_auth = _auth(
            is_fleet_user=False, fleet_token="", organization_id="",
            xlink_token="tok", xlink_user_id="uid",
        )
        with pytest.raises(CramerConnectAuthError):
            await client.get_devices(consumer_auth)

    async def test_xlink_devices_enriched_with_state_and_stats(self):
        """After list call, device-state is fetched and fields populated."""
        consumer_auth = _auth(
            is_fleet_user=False, fleet_token="", organization_id="",
            xlink_token="tok", xlink_user_id="uid",
        )
        client = _client_with_gets(
            _make_response(200, XLINK_DEVICE_LIST_OK),  # subscribe/devices
            _make_response(200, DEVICE_STATE_OK),        # device-state
        )
        devices = await client.get_devices(consumer_auth)

        assert len(devices) == 1
        d = devices[0]
        assert d.state == "4"
        assert d.state_label == "mowing"
        assert d.battery == 78
        assert d.next_start_ts == 1800000000
        assert d.cutting_time_s == 3600
        assert d.running_time_s == 7200
        assert d.charging_time_s == 1800
        assert d.error_count == 5
        assert d.distance_m == 10000      # 0x2710
        assert d.latitude == 52.0
        assert d.longitude == 5.0
        assert d.software_version == "13.5.100000000"
        assert d.sw_update_available is True
        assert d.mower_model == "Test RM1000"
        assert d.is_mower is True   # state is not None, no productCode → is_mower

    async def test_xlink_no_schedule_next_start_is_none(self):
        """next_start = 0xFFFFFFFF means no schedule → next_start_ts = None."""
        import json as _j
        dp32_no_sched = _j.dumps({
            "request": {"mower_main_state": 7, "battery_status": 100,
                        "next_start": 4294967295}
        })
        state_resp = {"datapoints": {"32": {"value": dp32_no_sched}}}
        consumer_auth = _auth(
            is_fleet_user=False, fleet_token="", organization_id="",
            xlink_token="tok", xlink_user_id="uid",
        )
        client = _client_with_gets(
            _make_response(200, XLINK_DEVICE_LIST_OK),
            _make_response(200, state_resp),
        )
        devices = await client.get_devices(consumer_auth)
        assert devices[0].next_start_ts is None

    async def test_xlink_zero_next_start_is_none(self):
        """next_start = 0 means the mower has no actionable next start."""
        import json as _j
        dp32_no_sched = _j.dumps({
            "request": {"mower_main_state": 2, "battery_status": 100,
                        "next_start": 0}
        })
        state_resp = {"datapoints": {"32": {"value": dp32_no_sched}}}
        consumer_auth = _auth(
            is_fleet_user=False, fleet_token="", organization_id="",
            xlink_token="tok", xlink_user_id="uid",
        )
        client = _client_with_gets(
            _make_response(200, XLINK_DEVICE_LIST_OK),
            _make_response(200, state_resp),
        )
        devices = await client.get_devices(consumer_auth)
        assert devices[0].next_start_ts is None

    async def test_xlink_device_state_failure_does_not_crash(self):
        """If device-state returns 500, device list still comes back."""
        consumer_auth = _auth(
            is_fleet_user=False, fleet_token="", organization_id="",
            xlink_token="tok", xlink_user_id="uid",
        )
        client = _client_with_gets(
            _make_response(200, XLINK_DEVICE_LIST_OK),
            _make_response(500, {}),
        )
        devices = await client.get_devices(consumer_auth)
        assert len(devices) == 1
        assert devices[0].state is None
        assert devices[0].battery is None

    async def test_xlink_distance_none_when_dp225_absent(self):
        """distance_m stays None when dp[225] is not in response."""
        import json as _j
        dp48_only = _j.dumps({"response": {"cutting_time": 1000, "running_time": 2000, "no_of_fatal_error": 0}})
        state_resp = {"datapoints": {"48": {"value": dp48_only}}}
        consumer_auth = _auth(
            is_fleet_user=False, fleet_token="", organization_id="",
            xlink_token="tok", xlink_user_id="uid",
        )
        client = _client_with_gets(
            _make_response(200, XLINK_DEVICE_LIST_OK),
            _make_response(200, state_resp),
        )
        devices = await client.get_devices(consumer_auth)
        assert devices[0].distance_m is None

    async def test_xlink_gps_none_when_dp34_absent(self):
        """latitude/longitude stay None when dp[34] is not in response."""
        import json as _j
        dp32_only = _j.dumps({"request": {"mower_main_state": 2, "battery_status": 80}})
        state_resp = {"datapoints": {"32": {"value": dp32_only}}}
        consumer_auth = _auth(
            is_fleet_user=False, fleet_token="", organization_id="",
            xlink_token="tok", xlink_user_id="uid",
        )
        client = _client_with_gets(
            _make_response(200, XLINK_DEVICE_LIST_OK),
            _make_response(200, state_resp),
        )
        devices = await client.get_devices(consumer_auth)
        assert devices[0].latitude is None
        assert devices[0].longitude is None

    async def test_xlink_sw_update_parsed(self):
        """sw_update_available is set from dp[117].response.sw_update."""
        import json as _j
        dp117 = _j.dumps({"request": {}, "response": {"return_code": 0, "sw_update": 0}})
        state_resp = {"datapoints": {"117": {"value": dp117}}}
        consumer_auth = _auth(
            is_fleet_user=False, fleet_token="", organization_id="",
            xlink_token="tok", xlink_user_id="uid",
        )
        client = _client_with_gets(
            _make_response(200, XLINK_DEVICE_LIST_OK),
            _make_response(200, state_resp),
        )
        devices = await client.get_devices(consumer_auth)
        assert devices[0].sw_update_available is False

    async def test_xlink_mower_model_stripped_of_nulls(self):
        """mower_model is cleaned of null bytes from dp[21].response.mower_name."""
        import json as _j
        dp21 = _j.dumps({"request": {}, "response": {"mower_name": "Test RM1000\x00\xff\xff"}})
        state_resp = {"datapoints": {"21": {"value": dp21}}}
        consumer_auth = _auth(
            is_fleet_user=False, fleet_token="", organization_id="",
            xlink_token="tok", xlink_user_id="uid",
        )
        client = _client_with_gets(
            _make_response(200, XLINK_DEVICE_LIST_OK),
            _make_response(200, state_resp),
        )
        devices = await client.get_devices(consumer_auth)
        assert devices[0].mower_model == "Test RM1000"


# ---------------------------------------------------------------------------
# CramerDevice helper properties
# ---------------------------------------------------------------------------

class TestCramerDevice:
    def _device(self, state, product_code="RLM1") -> CramerDevice:
        return CramerDevice(
            device_id="1", product_id="p", name="Mower",
            serial_number="SN", mac="", product_code=product_code,
            state=state, battery=80, is_online=True,
        )

    @pytest.mark.parametrize("state,expected", [
        ("4",  "mowing"),
        ("7",  "charging"),
        ("2",  "parked"),
        ("8",  "error"),
        ("12", "mowing_secondary_area"),
        (None, "unknown"),
        ("99", "unknown"),
    ])
    def test_state_label(self, state, expected):
        assert self._device(state).state_label == expected

    def test_rlm1_is_mower(self):
        assert self._device("4", "RLM1").is_mower is True

    def test_rlm2_is_mower(self):
        assert self._device("4", "RLM2").is_mower is True

    def test_other_product_is_not_mower(self):
        assert self._device("4", "BATTERY").is_mower is False

    def test_no_product_code_but_has_state_is_mower(self):
        """xlink devices have no productCode but state data marks them as mowers."""
        d = CramerDevice(
            device_id="1", product_id="p", name="Test Mower",
            serial_number="SN", mac="", product_code="",
            state="2", battery=99, is_online=True,
        )
        assert d.is_mower is True

    def test_no_product_code_no_state_is_not_mower(self):
        d = CramerDevice(
            device_id="1", product_id="p", name="Unknown",
            serial_number="SN", mac="", product_code="",
            state=None, battery=None, is_online=False,
        )
        assert d.is_mower is False


# ---------------------------------------------------------------------------
# Additions for app 4.5.0 parity: fleet xlink token, dp8/dp32/dp33, MQTT
# ---------------------------------------------------------------------------

import asyncio  # noqa: E402

from custom_components.cramer_connect.api import (  # noqa: E402
    CramerConnectTokenExpiredError,
    _mqtt_publish,
    build_park_command,
    build_start_command,
    build_stop_command,
)
from custom_components.cramer_connect.coordinator import (  # noqa: E402
    CramerConnectCoordinator,
)

FLEET_XLINK_OK = {
    "authString": "fleet-authorize",
    "authorized": True,
    "token": "fleet-xlink-token",
    "xlinkId": "987654",
}


class TestFleetXlinkToken:
    async def test_fleet_login_fetches_xlink_credentials(self):
        session = MagicMock()
        session.post = MagicMock(side_effect=[
            _make_response(200, IS_FLEET_TRUE),
            _make_response(200, FLEET_LOGIN_OK),
            _make_response(200, GUC_TOKEN_OK),
            _make_response(200, FLEET_XLINK_OK),
        ])
        auth = await CramerConnectClient(session).authenticate("a@b.c", "pw")
        assert auth.xlink_token == "fleet-xlink-token"
        assert auth.xlink_user_id == "987654"
        assert auth.xlink_authorize == "fleet-authorize"
        assert auth.has_mqtt_credentials
        url = session.post.call_args_list[3][0][0]
        assert url.endswith("/api/account/XlinkToken")
        assert session.post.call_args_list[3][1]["json"] == {"organizationId": "org-123"}

    async def test_xlink_token_failure_is_not_fatal(self):
        client = _client_with_posts(
            _make_response(200, IS_FLEET_TRUE),
            _make_response(200, FLEET_LOGIN_OK),
            _make_response(200, GUC_TOKEN_OK),
            _make_response(500, {"error": "boom"}),
        )
        auth = await client.authenticate("a@b.c", "pw")
        assert auth.guc_token == "guc-token-xyz"
        assert auth.xlink_token == ""
        assert not auth.has_mqtt_credentials

    async def test_fleet_devices_enriched_when_xlink_token_present(self):
        state = {"datapoints": {"32": {"value": DP32_VALUE}}}
        client = _client_with_gets(
            _make_response(200, DEVICE_LIST_OK),
            _make_response(200, state),
        )
        auth = _auth(xlink_token="t", xlink_user_id="u", xlink_authorize="a")
        devices = await client.get_devices(auth)
        assert devices[0].source_for_next_start == 2


class TestAuthExpiry:
    def test_consumer_expiry_capped_by_xlink_lifetime(self):
        assert _auth(guc_expires_in=86400, xlink_token="x").expires_in == 7200

    def test_shorter_guc_wins(self):
        assert _auth(guc_expires_in=3600, xlink_token="x").expires_in == 3600

    def test_fleet_without_xlink_uses_guc(self):
        assert _auth(guc_expires_in=86400).expires_in == 86400


class TestExtraDatapoints:
    async def _device_from(self, datapoints):
        consumer_auth = _auth(
            is_fleet_user=False, fleet_token="", organization_id="",
            xlink_token="tok", xlink_user_id="uid",
        )
        client = _client_with_gets(
            _make_response(200, XLINK_DEVICE_LIST_OK),
            _make_response(200, {"datapoints": datapoints}),
        )
        return (await client.get_devices(consumer_auth))[0]

    async def test_source_for_next_start(self):
        dev = await self._device_from({"32": {"value": DP32_VALUE}})
        assert dev.source_for_next_start == 2
        assert dev.next_start_reason == "parked_by_schedule"

    async def test_security_level_from_dp8(self):
        dp8 = json.dumps({"response": {"return_code": 0, "security_level": 1}})
        dev = await self._device_from({"8": {"value": dp8}})
        assert dev.security_level == 1
        assert dev.requires_pin

    async def test_security_level_ignored_on_error_return_code(self):
        dp8 = json.dumps({"response": {"return_code": 3, "security_level": 1}})
        dev = await self._device_from({"8": {"value": dp8}})
        assert dev.security_level is None
        assert not dev.requires_pin

    async def test_last_error_from_dp33(self):
        dp33 = json.dumps({"request": {"event_id": 47, "request_time": "2026-06-01T08:00:00Z"}})
        dev = await self._device_from({"33": {"value": dp33}})
        assert dev.last_error_code == 47
        assert dev.last_error == "Battery empty."
        assert dev.last_error_time == "2026-06-01T08:00:00Z"

    async def test_signed_minus_one_next_start_is_none(self):
        dp32 = json.dumps({"request": {"mower_main_state": 2, "next_start": -1}})
        dev = await self._device_from({"32": {"value": dp32}})
        assert dev.next_start_ts is None


class TestCommandBuilders:
    def test_start_without_pin(self):
        assert build_start_command() == "0007000d003a6000A007e4000400000000"

    def test_start_with_pin(self):
        assert build_start_command("1234") == "0007000d003a6000A007e400040000d204"

    def test_park_forever(self):
        assert build_park_command() == "0007000b003e6000A005e60002feff"

    def test_park_two_hours(self):
        assert build_park_command(120) == "0007000b003e6000A005e600027800"

    @pytest.mark.parametrize("minutes", [0, -5, 0xFFFE, 100000])
    def test_park_out_of_range(self, minutes):
        with pytest.raises(ValueError):
            build_park_command(minutes)

    def test_stop(self):
        dev = CramerDevice("1", "p", "n", "", "", "RLM1", "4", 50, True)
        assert build_stop_command(dev) == "0007000b00386000A005e200020000"

    def test_stop_secondary_area(self):
        dev = CramerDevice("1", "p", "n", "", "", "RLM1", "12", 50, True)
        assert build_stop_command(dev) == "0007000c00366000A0064a0103000000"

    def test_rlm2_not_remote_controllable(self):
        dev = CramerDevice("1", "p", "n", "", "", "RLM2", "4", 50, True)
        assert not dev.supports_remote_control


async def _fake_broker(connack_rc: int = 0):
    """Start a local TCP server that speaks just enough MQTT 3.1.1."""
    received: dict = {}

    async def read_packet(reader):
        header = (await reader.readexactly(1))[0]
        mult, length = 1, 0
        while True:
            b = (await reader.readexactly(1))[0]
            length += (b & 0x7F) * mult
            if not b & 0x80:
                break
            mult *= 128
        return header, await reader.readexactly(length)

    async def handle(reader, writer):
        header, body = await read_packet(reader)
        received["connect"] = (header, body)
        writer.write(bytes([0x20, 0x02, 0x00, connack_rc]))
        await writer.drain()
        if connack_rc:
            writer.close()
            return
        header, body = await read_packet(reader)
        received["publish"] = (header, body)
        writer.write(bytes([0x40, 0x02]) + body[2 + int.from_bytes(body[:2], "big"):][:2])
        await writer.drain()
        received["disconnect"] = await reader.readexactly(2)
        writer.close()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    return server, server.sockets[0].getsockname()[1], received


class TestMqttProtocol:
    async def test_publish_round_trip(self):
        server, port, received = await _fake_broker()
        async with server:
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            payload = bytes.fromhex(build_start_command())
            await _mqtt_publish(reader, writer, "X:APP;A:4;V:1;RES:abc;", "user-1",
                                "md5pass", "$7/100000001", payload)
            writer.close()

        header, body = received["connect"]
        assert header == 0x10
        assert body[:6] == b"\x00\x04MQTT"
        assert body[6] == 4 and body[7] == 0xC2
        assert b"user-1" in body and b"md5pass" in body

        header, body = received["publish"]
        assert header == 0x32  # QoS 1
        tlen = int.from_bytes(body[:2], "big")
        assert body[2:2 + tlen] == b"$7/100000001"
        assert body[2 + tlen + 2:] == payload
        assert received["disconnect"] == b"\xe0\x00"

    async def test_bad_credentials_raise_token_expired(self):
        server, port, _ = await _fake_broker(connack_rc=5)
        async with server:
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            with pytest.raises(CramerConnectTokenExpiredError):
                await _mqtt_publish(reader, writer, "c", "u", "p", "$7/1", b"\x00")
            writer.close()

    async def test_server_unavailable_raises_api_error(self):
        server, port, _ = await _fake_broker(connack_rc=3)
        async with server:
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            with pytest.raises(CramerConnectApiError) as exc:
                await _mqtt_publish(reader, writer, "c", "u", "p", "$7/1", b"\x00")
            assert not isinstance(exc.value, CramerConnectTokenExpiredError)
            writer.close()

    async def test_send_command_requires_credentials(self):
        client = CramerConnectClient(MagicMock())
        with pytest.raises(CramerConnectApiError):
            await client.send_command(_auth(), "1", "00")


class TestCoordinatorReauth:
    def _coord(self, client):
        coord = CramerConnectCoordinator.__new__(CramerConnectCoordinator)
        coord._client = client
        coord._auth = _auth()
        coord._username = "u"
        coord._password = "p"
        coord.pin = None
        coord._pending_schedules = {}
        coord._auth_lock = asyncio.Lock()
        return coord

    async def test_auth_error_triggers_single_reauth(self):
        dev = CramerDevice("1", "p", "n", "", "", "RLM1", "4", 50, True)
        client = MagicMock()
        client.get_devices = AsyncMock(side_effect=[CramerConnectAuthError("401"), [dev]])
        client.authenticate = AsyncMock(return_value=_auth(guc_token="fresh"))
        coord = self._coord(client)
        data = await coord._async_update_data()
        assert data == {"1": dev}
        client.authenticate.assert_awaited_once()
        assert coord.auth.guc_token == "fresh"

    async def test_command_retried_after_mqtt_login_refused(self):
        client = MagicMock()
        client.send_command = AsyncMock(side_effect=[CramerConnectTokenExpiredError("x"), None])
        client.authenticate = AsyncMock(return_value=_auth(guc_token="fresh"))
        coord = self._coord(client)
        await coord.async_send_command("1", "00")
        assert client.send_command.await_count == 2
        client.authenticate.assert_awaited_once()


class TestUiDatapoints:
    async def _device_from(self, datapoints):
        consumer_auth = _auth(
            is_fleet_user=False, fleet_token="", organization_id="",
            xlink_token="tok", xlink_user_id="uid",
        )
        client = _client_with_gets(
            _make_response(200, XLINK_DEVICE_LIST_OK),
            _make_response(200, {"datapoints": datapoints}),
        )
        return (await client.get_devices(consumer_auth))[0]

    async def test_last_seen_from_dp32_report_time(self):
        dev = await self._device_from({"32": {"report_time": "2026-11-05T04:33:05.273Z", "value": DP32_VALUE}})
        assert dev.last_seen.isoformat() == "2026-11-05T04:33:05.273000+00:00"

    async def test_signal_quality(self):
        dp31 = json.dumps({"response": {"return_code": 0, "signal_quality": 83}})
        dp36 = json.dumps({"response": {"return_code": 0, "gprs_lte_signal_quality": 93}})
        dev = await self._device_from({"31": {"value": dp31}, "36": {"value": dp36}})
        assert dev.wifi_signal == 83 and dev.lte_signal == 93

    async def test_installed_version_from_dp117_request(self):
        dev = await self._device_from({
            "117": {"value": DP117_VALUE},
            "246": {"value": "ignored"},
        })
        assert dev.software_version == "13.5.100000000"

    async def test_dp246_fallback(self):
        dev = await self._device_from({"246": {"value": "13.5.7"}})
        assert dev.software_version == "13.5.7"

    async def test_latest_version_from_dp119_header(self):
        # Real header from a mower: "#RLM@", 13.5, build 1775741529
        header = "23524c4d40000d0559aad7696400020100c40010003c07003f7dd655"
        dp119 = json.dumps({"response": {"return_code": 0, "program_header": header}})
        dev = await self._device_from({"119": {"value": dp119}})
        assert dev.latest_software_version == "13.5.1775741529"

    async def test_raw_datapoints_kept_for_diagnostics(self):
        dev = await self._device_from({"32": {"value": DP32_VALUE}})
        assert "32" in dev.datapoints


class TestDiagnostics:
    def test_location_and_ids_redacted(self):
        from custom_components.cramer_connect.diagnostics import device_diagnostics
        dp34 = json.dumps({"request": {"latitude": "50.8", "longitude": "4.2"}})
        dev = CramerDevice("1", "p", "Test Mower", "SN1", "aa", "RLM1", "4", 50, True,
                           latitude=50.8, longitude=4.2,
                           datapoints={"34": {"value": dp34}})
        out = device_diagnostics(dev)
        assert out["latitude"] == "**REDACTED**"
        assert out["serial_number"] == "**REDACTED**"
        assert out["name"] == "**REDACTED**"
        assert out["datapoints"]["34"]["value"]["request"]["latitude"] == "**REDACTED**"
        assert out["state_label"] == "mowing"


# ---------------------------------------------------------------------------
# Schedule (dp[125]) parsing and commands
# ---------------------------------------------------------------------------

from custom_components.cramer_connect.api import (  # noqa: E402
    OFF_TIMER,
    ScheduleTimer,
    build_nonstop_command,
    build_schedule_command,
    build_set_clock_command,
    parse_schedule,
)

_DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


def _dp125_response(overrides: dict | None = None) -> dict:
    """dp[125] response like the real one: only Tuesday 10:00 for 420 min."""
    resp = {"return_code": 0}
    for day in _DAYS:
        for n in (1, 2):
            p = f"{day}_timer_{n}_"
            resp.update({p + "start_time_hour": 0, p + "start_time_minute": 0,
                         p + "length_minutes": 0, p + "timer_mode": 0})
    resp.update({"tuesday_timer_1_start_time_hour": 10,
                 "tuesday_timer_1_length_minutes": 420,
                 "tuesday_timer_1_timer_mode": 1})
    resp.update(overrides or {})
    return resp


def _week(**days) -> tuple:
    return tuple(days.get(d, (OFF_TIMER, OFF_TIMER)) for d in _DAYS)


class TestScheduleParsing:
    def test_parse_real_layout(self):
        sched = parse_schedule(_dp125_response())
        assert sched[1][0] == ScheduleTimer(10, 0, 420, True)
        assert not sched[0][0].active and not sched[1][1].active

    def test_missing_key_returns_none(self):
        resp = _dp125_response()
        del resp["sunday_timer_2_timer_mode"]
        assert parse_schedule(resp) is None

    async def test_schedule_from_device_state(self):
        dp125 = json.dumps({"request": {}, "response": _dp125_response()})
        consumer_auth = _auth(is_fleet_user=False, fleet_token="", organization_id="",
                              xlink_token="tok", xlink_user_id="uid")
        client = _client_with_gets(
            _make_response(200, XLINK_DEVICE_LIST_OK),
            _make_response(200, {"datapoints": {"125": {"value": dp125}}}),
        )
        dev = (await client.get_devices(consumer_auth))[0]
        assert dev.schedule[1][0].length_minutes == 420


class TestScheduleCommand:
    def test_round_trip_matches_app_format(self):
        sched = _week(tuesday=(ScheduleTimer(10, 0, 420, True), OFF_TIMER))
        cmd = build_schedule_command(sched)
        assert cmd.startswith("0007004f00326000A049400146")
        body = bytes.fromhex(cmd[len("0007004f00326000A049400146"):])
        assert len(body) == 70
        # Tuesday timer 1: 0a 00 a401 01
        assert body[10:15] == bytes([0x0A, 0x00, 0xA4, 0x01, 0x01])
        assert body[:10] == bytes(10)

    def test_header_length_fields_consistent(self):
        cmd = bytes.fromhex(build_schedule_command(_week()))
        assert cmd[3] == len(cmd) - 4  # 0x4f
        assert cmd[9] == len(cmd) - 10  # 0x49

    def test_disabled_timer_sent_as_off(self):
        sched = _week(monday=(ScheduleTimer(9, 0, 60, False), OFF_TIMER))
        body = bytes.fromhex(build_schedule_command(sched)[26:])
        assert body[2:5] == bytes([0, 0, 0])

    def test_overlap_rejected(self):
        sched = _week(monday=(ScheduleTimer(9, 0, 120, True), ScheduleTimer(10, 0, 60, True)))
        with pytest.raises(ValueError, match="overlap"):
            build_schedule_command(sched)

    def test_past_midnight_rejected(self):
        sched = _week(monday=(ScheduleTimer(23, 0, 120, True), OFF_TIMER))
        with pytest.raises(ValueError, match="midnight"):
            build_schedule_command(sched)

    def test_until_midnight_allowed(self):
        sched = _week(monday=(ScheduleTimer(22, 0, 120, True), OFF_TIMER))
        build_schedule_command(sched)


class TestNonstopAndClock:
    def test_nonstop_two_days(self):
        # 2880 minutes = 0x0b40 -> "400b", then "01" (app preset "2 days")
        assert build_nonstop_command(2) == "0007000c00366000A0064a0103400b01"

    def test_cancel_nonstop(self):
        assert build_nonstop_command(None) == "0007000c00366000A0064a0103000000"

    @pytest.mark.parametrize("days", [0, 25])
    def test_nonstop_out_of_range(self, days):
        with pytest.raises(ValueError):
            build_nonstop_command(days)

    def test_set_clock_positive_offset(self):
        cmd = build_set_clock_command(0x69000000, 3600)
        assert cmd == "0007001100566000A00b9a0008" + "00000069" + "100e0000"

    def test_set_clock_negative_offset(self):
        # -18000 s (UTC-5) is two's complement, little-endian, as in the app
        cmd = build_set_clock_command(0x69000000, -18000)
        assert cmd.endswith("b0b9ffff")

    def test_nonstop_flag_from_source(self):
        dev = CramerDevice("1", "p", "n", "", "", "RLM1", "4", 50, True,
                           source_for_next_start=52)
        assert dev.nonstop_mowing


class TestPendingSchedule:
    def _coord(self):
        coord = CramerConnectCoordinator.__new__(CramerConnectCoordinator)
        coord._pending_schedules = {}
        coord.data = {}
        return coord

    def _dev(self, schedule):
        return CramerDevice("1", "p", "n", "", "", "RLM1", "4", 50, True, schedule=schedule)

    def test_pending_overrides_stale_cloud_copy(self):
        coord = self._coord()
        new = _week(monday=(ScheduleTimer(9, 0, 60, True), OFF_TIMER))
        coord.set_pending_schedule("1", new)
        data = {"1": self._dev(_week())}
        coord._apply_pending_schedules(data)
        assert data["1"].schedule == new
        assert "1" in coord._pending_schedules

    def test_pending_cleared_once_cloud_matches(self):
        coord = self._coord()
        new = _week(monday=(ScheduleTimer(9, 0, 60, True), OFF_TIMER))
        coord.set_pending_schedule("1", new)
        coord._apply_pending_schedules({"1": self._dev(new)})
        assert coord._pending_schedules == {}

    def test_pending_expires(self):
        coord = self._coord()
        new = _week(monday=(ScheduleTimer(9, 0, 60, True), OFF_TIMER))
        coord._pending_schedules["1"] = (new, 0.0)  # already expired
        data = {"1": self._dev(_week())}
        coord._apply_pending_schedules(data)
        assert data["1"].schedule == _week()


# ---------------------------------------------------------------------------
# Robustness fixes (reported in PR #4)
# ---------------------------------------------------------------------------

class TestDatapointAuthFailure:
    async def test_device_state_401_raises_auth_error(self):
        consumer_auth = _auth(is_fleet_user=False, fleet_token="", organization_id="",
                              xlink_token="tok", xlink_user_id="uid")
        client = _client_with_gets(
            _make_response(200, XLINK_DEVICE_LIST_OK),
            _make_response(401, {"error": "expired"}),
        )
        with pytest.raises(CramerConnectAuthError):
            await client.get_devices(consumer_auth)

    async def test_device_state_500_still_degrades_gracefully(self):
        consumer_auth = _auth(is_fleet_user=False, fleet_token="", organization_id="",
                              xlink_token="tok", xlink_user_id="uid")
        client = _client_with_gets(
            _make_response(200, XLINK_DEVICE_LIST_OK),
            _make_response(500, {}),
        )
        devices = await client.get_devices(consumer_auth)
        assert len(devices) == 1 and devices[0].state is None

    async def test_coordinator_reauths_once_on_datapoint_401(self):
        dev = CramerDevice("1", "p", "n", "", "", "RLM1", "4", 50, True)
        client = MagicMock()
        client.get_devices = AsyncMock(side_effect=[CramerConnectAuthError("401"), [dev]])
        client.authenticate = AsyncMock(return_value=_auth(guc_token="fresh"))
        coord = TestCoordinatorReauth()._coord(client)
        assert await coord._async_update_data() == {"1": dev}
        client.authenticate.assert_awaited_once()


class TestConcurrentReauth:
    async def test_simultaneous_reauth_logs_in_once(self):
        gate = asyncio.Event()

        async def slow_login(*_):
            await gate.wait()
            return _auth(guc_token="fresh")

        client = MagicMock()
        client.authenticate = AsyncMock(side_effect=slow_login)
        coord = TestCoordinatorReauth()._coord(client)
        first = asyncio.create_task(coord.force_reauth())
        second = asyncio.create_task(coord.force_reauth())
        await asyncio.sleep(0)
        gate.set()
        await asyncio.gather(first, second)
        client.authenticate.assert_awaited_once()
        assert coord.auth.guc_token == "fresh"

    async def test_later_reauth_still_logs_in(self):
        client = MagicMock()
        client.authenticate = AsyncMock(side_effect=[_auth(guc_token="a"), _auth(guc_token="b")])
        coord = TestCoordinatorReauth()._coord(client)
        await coord.force_reauth()
        await coord.force_reauth()
        assert client.authenticate.await_count == 2
        assert coord.auth.guc_token == "b"


class TestScheduleBounds:
    @pytest.mark.parametrize("timer", [
        ScheduleTimer(24, 0, 0, False),   # inactive but invalid hour
        ScheduleTimer(10, 60, 0, False),  # invalid minute
        ScheduleTimer(10, 0, 1441, False),  # length beyond a day
        ScheduleTimer(10, 0, -1, True),
    ])
    def test_out_of_range_values_rejected_before_packing(self, timer):
        with pytest.raises(ValueError):
            build_schedule_command(_week(monday=(timer, OFF_TIMER)))


class TestDiagnosticsRedaction:
    def test_token_like_keys_redacted_inside_datapoints(self):
        from custom_components.cramer_connect.diagnostics import device_diagnostics
        dp = json.dumps({"response": {"access_token": "SECRET", "nested": {"psk": "SECRET"}}})
        dev = CramerDevice("1", "p", "n", "", "", "RLM1", "4", 50, True,
                           datapoints={"99": {"value": dp}})
        out = device_diagnostics(dev)
        assert "SECRET" not in json.dumps(out, default=str)
