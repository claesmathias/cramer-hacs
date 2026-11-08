"""Live integration test for the Cramer Connect login flow.

Run with:
    pytest tests/test_login_live.py -v -s --username YOUR_EMAIL --password YOUR_PASSWORD

Or via environment variables:
    CRAMER_USERNAME=YOUR_EMAIL CRAMER_PASSWORD=YOUR_PASSWORD pytest tests/test_login_live.py -v -s

Or put them in a .env file in the repo root (git-ignored):
    CRAMER_USERNAME=you@example.com
    CRAMER_PASSWORD=your-password
"""
import os
from pathlib import Path

import aiohttp
import pytest

_ENV_FILE = Path(__file__).parent.parent / ".env"


def _from_env_file(key: str) -> str | None:
    """Read KEY=VALUE from the repo's .env file (quotes optional)."""
    if not _ENV_FILE.is_file():
        return None
    for line in _ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        if name.strip().removeprefix("export ").strip() == key:
            return value.strip().strip("\"'") or None
    return None


@pytest.fixture
def username(request):
    un = (
        request.config.getoption("--username")
        or os.environ.get("CRAMER_USERNAME")
        or _from_env_file("CRAMER_USERNAME")
    )
    if not un:
        pytest.skip("No username provided — use --username, CRAMER_USERNAME env var or .env")
    return un


@pytest.fixture
def password(request):
    pw = (
        request.config.getoption("--password")
        or os.environ.get("CRAMER_PASSWORD")
        or _from_env_file("CRAMER_PASSWORD")
    )
    if not pw:
        pytest.skip("No password provided — use --password, CRAMER_PASSWORD env var or .env")
    return pw


@pytest.fixture
async def client():
    async with aiohttp.ClientSession() as session:
        from custom_components.cramer_connect.api import CramerConnectClient
        yield CramerConnectClient(session)


class TestLiveLogin:
    async def test_login_returns_tokens(self, client, username, password):
        auth = await client.authenticate(username, password)

        print(f"\nis_fleet_user : {auth.is_fleet_user}")
        if auth.is_fleet_user:
            print(f"fleet_token   : {auth.fleet_token[:40]}...")
            print(f"organization  : {auth.organization_id}")
        else:
            print(f"xlink_token   : {auth.xlink_token[:40]}...")
            print(f"xlink_user_id : {auth.xlink_user_id}")
        print(f"guc_token     : {auth.guc_token[:40]}...")
        print(f"guc_expires   : {auth.guc_expires_in}s")

        assert auth.guc_token, "guc_token should not be empty"
        assert auth.guc_expires_in > 0
        if auth.is_fleet_user:
            assert auth.fleet_token, "fleet_token should not be empty for fleet users"
            assert auth.organization_id, "organization_id should not be empty for fleet users"
        else:
            assert auth.xlink_token, "xlink_token should not be empty for consumer users"
            assert auth.xlink_user_id, "xlink_user_id should not be empty for consumer users"

    async def test_devices_listed_after_login(self, client, username, password):
        auth = await client.authenticate(username, password)
        devices = await client.get_devices(auth)

        print(f"\nFound {len(devices)} device(s):")
        for d in devices:
            print(f"  [{d.product_code or 'no-code'}] {d.name!r}")
            print(f"    state={d.state_label}  battery={d.battery}%  online={d.is_online}")
            print(f"    next_start_ts={d.next_start_ts}")
            print(f"    cutting_time_s={d.cutting_time_s}  running_time_s={d.running_time_s}")
            print(f"    error_count={d.error_count}  distance_m={d.distance_m}")
            print(f"    latitude={d.latitude}  longitude={d.longitude}")

        assert isinstance(devices, list), "get_devices should return a list"

    async def test_raw_device_state_datapoints(self, client, username, password):
        """Dump every raw datapoint so we can discover new fields."""
        import json as _json
        auth = await client.authenticate(username, password)

        if auth.is_fleet_user:
            pytest.skip("raw datapoint dump only for xlink (consumer) accounts")

        import aiohttp as _aio
        from custom_components.cramer_connect.const import XLINK_URL, APP_APPLICATION_KEY, APP_BRAND, APP_NAME

        # Re-fetch the raw device list to get product_id
        async with _aio.ClientSession() as raw_session:
            headers = {
                "ApplicationKey": APP_APPLICATION_KEY,
                "Brand": APP_BRAND,
                "App-Name": APP_NAME,
                "Language": "en",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Access-Token": auth.xlink_token,
                "Xlink-Access-Token": auth.xlink_token,
                "Xlink-User-Id": auth.xlink_user_id,
            }
            url = f"{XLINK_URL}/v2/user/{auth.xlink_user_id}/subscribe/devices"
            async with raw_session.get(url, headers=headers) as resp:
                devices_raw = await resp.json()

            for item in devices_raw:
                product_id = item.get("product_id", "")
                device_id = str(item.get("id", ""))
                name = item.get("name", "unknown")
                print(f"\n=== {name} (product_id={product_id}, device_id={device_id}) ===")
                print("  Raw device fields:")
                for k, v in item.items():
                    if k not in ("product_id", "id", "name"):
                        print(f"    {k}: {v!r}")

                state_url = f"{XLINK_URL}/v2/product/{product_id}/device-state/{device_id}"
                async with raw_session.get(state_url, headers=headers) as sresp:
                    if sresp.status != 200:
                        print(f"  device-state returned {sresp.status}")
                        continue
                    state_data = await sresp.json()

                datapoints = state_data.get("datapoints") or {}
                for dp_key in sorted(datapoints.keys(), key=lambda k: int(k) if k.isdigit() else 999):
                    dp = datapoints[dp_key]
                    value = dp.get("value")
                    if isinstance(value, str):
                        try:
                            parsed = _json.loads(value)
                            print(f"  dp[{dp_key}] = {_json.dumps(parsed, indent=4)}")
                        except Exception:
                            print(f"  dp[{dp_key}] = {value!r}")
                    else:
                        print(f"  dp[{dp_key}] = {value!r}")

    async def test_mqtt_login(self, client, username, password):
        """Log in to the MQTT command broker (CONNECT/CONNACK only).

        No command is published, so the mower is not affected.
        """
        import asyncio
        import hashlib
        import ssl

        from custom_components.cramer_connect.api import _mqtt_packet, _mqtt_read_packet, _mqtt_str
        from custom_components.cramer_connect.const import MQTT_HOST, MQTT_PORT

        auth = await client.authenticate(username, password)
        if not auth.has_mqtt_credentials:
            pytest.skip("Account has no xlink/MQTT credentials")

        password_md5 = hashlib.md5(
            (auth.xlink_user_id + auth.xlink_authorize).encode()
        ).hexdigest()
        reader, writer = await asyncio.open_connection(
            MQTT_HOST, MQTT_PORT, ssl=ssl.create_default_context(),
            server_hostname=MQTT_HOST,
        )
        try:
            connect = (
                _mqtt_str("MQTT") + bytes([0x04, 0xC2]) + (60).to_bytes(2, "big")
                + _mqtt_str("X:APP;A:4;V:1;RES:0000000000000000;")
                + _mqtt_str(auth.xlink_user_id) + _mqtt_str(password_md5)
            )
            writer.write(_mqtt_packet(0x10, connect))
            await writer.drain()
            header, body = await asyncio.wait_for(_mqtt_read_packet(reader), 10)
            print(f"\nCONNACK header=0x{header:02x} body={body.hex()}")
            assert header >> 4 == 2
            assert body[1] == 0, f"MQTT login refused, return code {body[1]}"
            writer.write(b"\xe0\x00")
            await writer.drain()
        finally:
            writer.close()
