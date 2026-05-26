"""Live integration test for the Cramer Connect login flow.

Run with:
    pytest tests/test_login_live.py -v -s --username YOUR_EMAIL --password YOUR_PASSWORD

Or via environment variables:
    CRAMER_USERNAME=YOUR_EMAIL CRAMER_PASSWORD=YOUR_PASSWORD pytest tests/test_login_live.py -v -s
"""
import os

import aiohttp
import pytest


@pytest.fixture
def username(request):
    un = request.config.getoption("--username") or os.environ.get("CRAMER_USERNAME")
    if not un:
        pytest.skip("No username provided — use --username or CRAMER_USERNAME env var")
    return un


@pytest.fixture
def password(request):
    pw = request.config.getoption("--password") or os.environ.get("CRAMER_PASSWORD")
    if not pw:
        pytest.skip("No password provided — use --password or CRAMER_PASSWORD env var")
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
