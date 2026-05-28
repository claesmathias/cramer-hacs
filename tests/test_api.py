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

    async def test_user_exist_failure_falls_back_to_consumer(self):
        """Non-200 from user-exist should fall back to consumer path."""
        client = _client_with_posts(
            _make_response(500, {}),
            _make_response(200, XLINK_LOGIN_OK),
            _make_response(200, GUC_DIRECT_OK),
        )
        auth = await client.authenticate("consumer@example.com", "secret")
        assert auth.is_fleet_user is False


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
            xlink_token="my-xlink-token",
            xlink_user_id="u-99",
        )
        await client.get_devices(consumer_auth)

        _, kwargs = session.get.call_args
        assert kwargs["headers"]["Access-Token"] == "my-xlink-token"
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
