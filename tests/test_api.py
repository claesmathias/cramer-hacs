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

DEVICE_LIST_OK = [
    {
        "id": 12345,
        "product_id": "prod-001",
        "name": "My Mower",
        "sn": "SN001",
        "mac": "AA:BB:CC:DD:EE:FF",
        "productCode": "RLM1",
        "state": 4,
        "battery": 78,
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
