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

    async def test_probe_write_endpoint(self, client, username, password):
        """Probe candidate write endpoint paths to find the correct one.

        This test sends a harmless empty payload to several candidate URLs
        and prints the HTTP status for each. A 2xx or 4xx (not 404) means
        the path exists; 404 means it doesn't.
        """
        import aiohttp as _aio
        from custom_components.cramer_connect.const import (
            XLINK_URL, APP_APPLICATION_KEY, APP_BRAND, APP_NAME,
        )

        auth = await client.authenticate(username, password)
        if auth.is_fleet_user:
            pytest.skip("write endpoint probe only for xlink (consumer) accounts")

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

            # Get a real device_id / product_id
            url = f"{XLINK_URL}/v2/user/{auth.xlink_user_id}/subscribe/devices"
            async with raw_session.get(url, headers=headers) as resp:
                devices_raw = await resp.json()

            if not devices_raw:
                pytest.skip("No devices found")

            item = devices_raw[0]
            product_id = item.get("product_id", "")
            device_id = str(item.get("id", ""))
            print(f"\nProbing write endpoints for device {device_id} (product {product_id})")

            from custom_components.cramer_connect.const import GUC_URL

            # Get per-device authorize_code
            device_authorize_code = str(item.get("authorize_code", ""))
            user_authorize = auth.xlink_authorize
            print(f"  xlink_authorize (user) = {user_authorize!r}")
            print(f"  authorize_code (device) = {device_authorize_code!r}")

            base_no_token = {k: v for k, v in headers.items() if k not in ("Access-Token", "Xlink-Access-Token")}

            # --- Part 1: xlink PUT /device-state with all auth combos ---
            write_url = f"{XLINK_URL}/v2/product/{product_id}/device-state/{device_id}"
            print(f"\n[A] xlink PUT {write_url.replace(XLINK_URL, '')}:")
            xlink_variants = [
                ("user token only",                    {**headers}),
                ("user token + Authorize: dev_code",   {**headers, "Authorize": device_authorize_code}),
                ("dev_code as Access-Token",           {**base_no_token, "Access-Token": device_authorize_code, "Xlink-Access-Token": device_authorize_code}),
                ("dev_code as Access + user Authorize",{**base_no_token, "Access-Token": device_authorize_code, "Xlink-Access-Token": device_authorize_code, "Authorize": auth.xlink_token}),
                ("GUC Bearer + user token",            {**headers, "Authorization": f"Bearer {auth.guc_token}"}),
            ]
            for label, h in xlink_variants:
                async with raw_session.put(write_url, json={}, headers=h) as resp:
                    body = await resp.text()
                    ok = resp.status in (200, 204)
                    print(f"  {'✓ OK' if ok else '✗   '}  [{label}]  → {resp.status}: {body[:100]}")

            # --- Part 2: GUC API write endpoint candidates ---
            guc_headers = {
                **{k: v for k, v in headers.items() if k not in ("Access-Token", "Xlink-Access-Token", "Xlink-User-Id")},
                "Authorization": f"Bearer {auth.guc_token}",
            }
            guc_candidates = [
                ("POST", f"{GUC_URL}/api/v1/device/{device_id}/command"),
                ("POST", f"{GUC_URL}/api/v1/product/{product_id}/device/{device_id}/command"),
                ("POST", f"{GUC_URL}/api/iot/device/{device_id}/dp-write"),
                ("POST", f"{GUC_URL}/api/iot/product/{product_id}/device/{device_id}/dp-write"),
                ("PUT",  f"{GUC_URL}/api/iot/product/{product_id}/device/{device_id}/state"),
                ("POST", f"{GUC_URL}/api/device/{device_id}/control"),
                ("POST", f"{GUC_URL}/api/product/{product_id}/device/{device_id}/ctrl"),
                ("POST", f"{GUC_URL}/api/product/{product_id}/dp-write/{device_id}"),
                ("POST", f"{GUC_URL}/api/xlink/product/{product_id}/device/{device_id}/ctrl"),
            ]
            print(f"\n[B] GUC API ({GUC_URL}) write candidates:")
            for method, guc_url in guc_candidates:
                try:
                    async with raw_session.request(method, guc_url, json={}, headers=guc_headers) as resp:
                        body = await resp.text()
                        ok = resp.status not in (404, 405, 503)
                        print(f"  {'✓ PATH EXISTS' if ok else '✗ '+str(resp.status)+'       '}  {method} {guc_url.replace(GUC_URL, '')}  → {resp.status}: {body[:80]}")
                except Exception as e:
                    print(f"  ✗ ERROR  {method} {guc_url.replace(GUC_URL, '')}  → {e}")

            # --- Part 3: Fleet API with GUC bearer (consumer path) ---
            from custom_components.cramer_connect.const import FLEET_API_URL
            fleet_headers = {
                **{k: v for k, v in headers.items() if k not in ("Access-Token", "Xlink-Access-Token", "Xlink-User-Id")},
                "Authorization": f"Bearer {auth.guc_token}",
            }
            fleet_candidates = [
                ("POST", f"{FLEET_API_URL}/api/devices/{device_id}/command"),
                ("POST", f"{FLEET_API_URL}/api/devices/command/{product_id}/{device_id}"),
                ("POST", f"{FLEET_API_URL}/api/device/{device_id}/control"),
                ("PUT",  f"{FLEET_API_URL}/api/devices/{device_id}/status"),
                ("POST", f"{FLEET_API_URL}/api/command/{device_id}"),
            ]
            print(f"\n[C] Fleet API ({FLEET_API_URL}) with GUC bearer:")
            for method, furl in fleet_candidates:
                try:
                    async with raw_session.request(method, furl, json={}, headers=fleet_headers) as resp:
                        body = await resp.text()
                        ok = resp.status not in (404, 405, 503)
                        print(f"  {'✓ PATH EXISTS' if ok else '✗ '+str(resp.status)+'       '}  {method} {furl.replace(FLEET_API_URL,'')}  → {resp.status}: {body[:80]}")
                except Exception as e:
                    print(f"  ✗ ERROR  {furl.replace(FLEET_API_URL,'')}  → {e}")

            # --- Part 4: GUC API with xlink token instead of GUC bearer ---
            xlink_guc_headers = {**guc_headers, "Access-Token": auth.xlink_token}
            print(f"\n[D] GUC API with xlink Access-Token (top 3 paths):")
            for method, guc_url in guc_candidates[:3]:
                try:
                    async with raw_session.request(method, guc_url, json={}, headers=xlink_guc_headers) as resp:
                        body = await resp.text()
                        ok = resp.status not in (404, 405, 503)
                        print(f"  {'✓ PATH EXISTS' if ok else '✗ '+str(resp.status)+'       '}  {method} {guc_url.replace(GUC_URL,'')}  → {resp.status}: {body[:80]}")
                except Exception as e:
                    print(f"  ✗ ERROR  → {e}")
