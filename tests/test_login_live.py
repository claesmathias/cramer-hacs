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

            # --- Part 0a: app_datapoint_value (known endpoint, testing again) ---
            app_dp_url = f"{XLINK_URL}/v2/product/{product_id}/app_datapoint_value"
            app_dp_payload = {
                "device_id": int(device_id),
                "datapoints": {"97": {"value": '{"request":{"park_time":0,"park_reason":1}}'}},
            }
            print(f"\n[0a] app_datapoint_value POST:")
            async with raw_session.post(app_dp_url, json=app_dp_payload, headers=headers) as resp:
                body = await resp.text()
                ok = resp.status in (200, 201, 204)
                print(f"  {'✓ OK' if ok else '✗   '}  → {resp.status}: {body[:200]}")

            # --- Part 0b: device property endpoints (APK: setDeviceProperty) ---
            prop_base = f"{XLINK_URL}/v2/product/{product_id}/device/{device_id}/property"
            print(f"\n[0b] device property endpoints (xlink token):")
            # GET all properties first
            async with raw_session.get(prop_base, headers=headers) as resp:
                body = await resp.text()
                print(f"  GET  /property  → {resp.status}: {body[:300]}")
            # PUT specific property keys
            for key, val in [("park", {"value": "1"}), ("pause", {"value": "1"}),
                              ("power", {"value": "1"}), ("operate", {"value": "1"})]:
                async with raw_session.put(f"{prop_base}/{key}", json=val, headers=headers) as resp:
                    body = await resp.text()
                    ok = resp.status in (200, 201, 204)
                    print(f"  {'✓ OK' if ok else '✗   '}  PUT /property/{key}  → {resp.status}: {body[:120]}")

            # --- Part 0c: try to get a write-capable XlinkToken via fleet API ---
            from custom_components.cramer_connect.const import FLEET_API_URL, DEVICE_API_URL
            base_app_headers = {k: v for k, v in headers.items() if k not in ("Access-Token", "Xlink-Access-Token", "Xlink-User-Id")}
            fleet_h = {**base_app_headers, "Authorization": f"Bearer {auth.guc_token}"}
            print(f"\n[0c] Fleet API: get XlinkToken with GUC bearer:")
            xlink_write_token = None
            async with raw_session.post(
                f"{FLEET_API_URL}/api/account/XlinkToken",
                json={"userId": auth.xlink_user_id},
                headers=fleet_h,
            ) as resp:
                body = await resp.text()
                ok = resp.status in (200, 201)
                print(f"  {'✓ OK' if ok else '✗   '}  → {resp.status}: {body[:200]}")
                if ok:
                    import json as _j
                    xlink_write_token = _j.loads(body).get("accessToken") or _j.loads(body).get("access_token")
                    print(f"  xlink_write_token = {xlink_write_token!r}")

            # If we got a write token, try property PUT with it
            if xlink_write_token:
                wh = {**headers, "Access-Token": xlink_write_token, "Xlink-Access-Token": xlink_write_token}
                async with raw_session.put(f"{prop_base}/park", json={"value": "1"}, headers=wh) as resp:
                    body = await resp.text()
                    print(f"  PUT /property/park with write token → {resp.status}: {body[:120]}")

            # --- Part 0f: SignalR method name probe ---
            from custom_components.cramer_connect.const import SIGNALR_URL
            import asyncio as _asyncio
            import json as _sj
            import aiohttp as _aio2
            _SR_TERM = "\x1e"

            signalr_headers = {**base_app_headers, "Authorization": f"Bearer {auth.guc_token}"}

            async def _try_hub_method(method_name: str, args: list) -> str:
                """Returns 'OK', 'no_method', or the error string."""
                neg_url = f"{SIGNALR_URL}/negotiate?negotiateVersion=1"
                async with raw_session.post(neg_url, headers=signalr_headers) as r:
                    if r.status != 200:
                        return f"negotiate_{r.status}"
                    neg = await r.json()
                token = neg.get("connectionToken", "")
                ws_url = SIGNALR_URL.replace("https://", "wss://") + f"?id={token}"
                invocation = _sj.dumps({"type": 1, "invocationId": "0", "target": method_name, "arguments": args}) + _SR_TERM
                try:
                    async with raw_session.ws_connect(ws_url, headers=signalr_headers) as ws:
                        await ws.send_str(_sj.dumps({"protocol": "json", "version": 1}) + _SR_TERM)
                        await _asyncio.wait_for(ws.receive(), timeout=3)
                        await ws.send_str(invocation)
                        for _ in range(5):
                            try:
                                msg = await _asyncio.wait_for(ws.receive(), timeout=3)
                            except _asyncio.TimeoutError:
                                return "timeout"
                            if msg.type == _aio2.WSMsgType.TEXT:
                                for part in msg.data.split(_SR_TERM):
                                    if not part.strip():
                                        continue
                                    try:
                                        p = _sj.loads(part)
                                    except ValueError:
                                        continue
                                    if p.get("type") == 3:
                                        err = p.get("error", "")
                                        if "does not exist" in err:
                                            return "no_method"
                                        return f"OK" if not err else f"err:{err[:80]}"
                        return "no_response"
                except Exception as e:
                    return f"ex:{e}"

            dev_args   = [{"deviceId": int(device_id), "productId": product_id}]
            snake_args = [{"device_id": int(device_id), "product_id": product_id}]
            pos_args   = [int(device_id), product_id]
            handle_args= [{"$type": "ParkMowerRequest", "deviceId": int(device_id), "productId": product_id}]
            candidates = [
                # PascalCase / camelCase without suffix
                ("ParkMower",           dev_args),
                ("parkMower",           dev_args),
                ("Park",                dev_args),
                ("park",                dev_args),
                # Generic dispatch patterns
                ("Handle",              handle_args),
                ("Dispatch",            handle_args),
                ("Process",             handle_args),
                ("Send",                [{"type": "ParkMowerRequest", "deviceId": int(device_id)}]),
                ("Command",             [{"type": "park", "deviceId": int(device_id)}]),
                # Positional args
                ("ParkMower",           pos_args),
                # Snake_case
                ("ParkMower",           snake_args),
                # Simple verbs
                ("park",                [int(device_id)]),
                ("start",               [int(device_id)]),
                ("pause",               [int(device_id)]),
                # With string device_id
                ("ParkMower",           [{"deviceId": device_id, "productId": product_id}]),
            ]
            print(f"\n[0f] SignalR method probe on mowerSupport hub:")
            for method, args in candidates[:6]:  # just first 6 - we know rest fail
                result = await _try_hub_method(method, args)
                icon = "✓" if result == "OK" else ("?" if result not in ("no_method", "no_response") else "✗")
                print(f"  {icon}  {method:30s} → {result}")

            # Probe other hub names on signalr.globetools.systems:446
            print(f"\n[0g] Other hub names on signalr.globetools.systems:446:")
            other_hubs = ["mowerControl", "control", "command", "device", "mowing",
                          "mower", "iotHub", "deviceControl", "CommandHub"]
            base_signalr = "https://signalr.globetools.systems:446"
            for hub in other_hubs:
                hub_url = f"{base_signalr}/{hub}"
                try:
                    async with raw_session.post(
                        f"{hub_url}/negotiate?negotiateVersion=1", headers=signalr_headers
                    ) as r:
                        body = await r.text()
                        ok = r.status == 200
                        print(f"  {'✓' if ok else '✗'}  /{hub}  → {r.status}: {body[:100]}")
                except Exception as e:
                    print(f"  ?  /{hub}  → {e}")

            # Listen to mowerSupport for 5 s to see what server pushes
            print(f"\n[0h] Listening to mowerSupport for server-pushed messages:")
            neg_url2 = f"{SIGNALR_URL}/negotiate?negotiateVersion=1"
            async with raw_session.post(neg_url2, headers=signalr_headers) as r:
                neg2 = await r.json()
            ws_url2 = SIGNALR_URL.replace("https://", "wss://") + f"?id={neg2['connectionToken']}"
            async with raw_session.ws_connect(ws_url2, headers=signalr_headers) as ws:
                await ws.send_str(_sj.dumps({"protocol": "json", "version": 1}) + _SR_TERM)
                await _asyncio.wait_for(ws.receive(), timeout=3)  # ack
                print(f"  Connected. Waiting 5 s for server messages...")
                try:
                    for _ in range(10):
                        msg = await _asyncio.wait_for(ws.receive(), timeout=0.5)
                        if msg.type == _aio2.WSMsgType.TEXT and msg.data.strip(_SR_TERM):
                            print(f"  SERVER→CLIENT: {msg.data[:300]}")
                except _asyncio.TimeoutError:
                    print(f"  (no server messages in 5 s)")

            # --- Part 0j: v_device write with token refresh ---
            from custom_components.cramer_connect.const import XLINK_CORP_ID
            print(f"\n[0j] v_device write + token refresh:")

            refreshed_token = None
            async with raw_session.post(
                f"{XLINK_URL}/v2/user/token/refresh",
                json={"corp_id": XLINK_CORP_ID, "refresh_token": auth.xlink_refresh_token},
                headers=headers,
            ) as r:
                body = await r.text()
                print(f"  token/refresh (refresh_token={auth.xlink_refresh_token[:10]}...)  → {r.status}: {body[:200]}")
                if r.status == 200:
                    import json as _jj
                    refreshed_token = _jj.loads(body).get("access_token")
                    print(f"  refreshed_token = {refreshed_token!r}")

            v_device_url = f"{XLINK_URL}/v2/product/{product_id}/v_device/{device_id}"
            cmd_payload = {"97": '{"request":{"park_time":0,"park_reason":1}}'}

            auth_combos = [
                ("user token",         headers),
                ("dev authorize_code", {**base_no_token, "Access-Token": device_authorize_code, "Xlink-Access-Token": device_authorize_code}),
            ]
            if refreshed_token:
                auth_combos.append(("refreshed", {**headers, "Access-Token": refreshed_token, "Xlink-Access-Token": refreshed_token}))

            for label, h in auth_combos:
                for method in ("POST", "PUT"):
                    async with raw_session.request(method, v_device_url, json=cmd_payload, headers=h) as r:
                        body = await r.text()
                        ok = r.status in (200, 201, 204)
                        print(f"  {'✓ OK' if ok else '✗   '}  {method} v_device [{label}]  → {r.status}: {body[:100]}")

            # --- Part 0k: RLM-specific xlink endpoints (from APK) ---
            serial_number = str(item.get("sn", ""))
            mac = str(item.get("mac", ""))
            print(f"\n[0k] RLM-specific xlink endpoints (sn={serial_number}):")
            rlm_candidates = [
                ("GET",  f"{XLINK_URL}/v2/rlm/validation/sn/{serial_number}"),
                ("GET",  f"{XLINK_URL}/v2/service/rlm2/device/psk"),
                ("POST", f"{XLINK_URL}/v2/service/rlm2/device/psk"),
                ("GET",  f"{XLINK_URL}/v2/service/rlm2/device/user/add"),
                ("POST", f"{XLINK_URL}/v2/service/rlm2/device/user/add"),
                ("GET",  f"{XLINK_URL}/v2/rlm/device/pairing"),
                ("POST", f"{XLINK_URL}/v2/rlm/device/pairing"),
            ]
            rlm_payload = {"device_id": int(device_id), "product_id": product_id,
                           "sn": serial_number}
            for method, rurl in rlm_candidates:
                try:
                    async with raw_session.request(method, rurl, json=rlm_payload, headers=headers) as r:
                        body = await r.text()
                        ok = r.status not in (404, 405)
                        print(f"  {'✓ PATH' if ok else '✗ '+str(r.status)+'  '}  {method} {rurl.replace(XLINK_URL,'')}  → {r.status}: {body[:150]}")
                except Exception as e:
                    print(f"  ? ERROR  {method}  → {e}")

            # --- Part 0i: idds.globetools.systems (IotDDSApi scope in GUC token) ---
            idds_base = "https://idds.globetools.systems"
            idds_h = {**base_app_headers, "Authorization": f"Bearer {auth.guc_token}"}
            idds_candidates = [
                ("GET",  f"{idds_base}/api/vehicle/{serial_number}"),
                ("GET",  f"{idds_base}/api/vehicle/mac/{mac}"),
                ("POST", f"{idds_base}/api/vehicle/{serial_number}/command"),
                ("POST", f"{idds_base}/api/vehicle/{serial_number}/control"),
                ("POST", f"{idds_base}/api/vehicle/{serial_number}/datapoint"),
                ("GET",  f"{idds_base}/api/vehicle/{device_id}"),
                ("POST", f"{idds_base}/api/vehicle/{device_id}/command"),
                ("GET",  f"{idds_base}/api/device/{serial_number}"),
                ("POST", f"{idds_base}/api/device/{serial_number}/command"),
                ("GET",  f"{idds_base}/api/mower/{serial_number}"),
            ]
            print(f"\n[0i] idds.globetools.systems (IotDDSApi, sn={serial_number}, mac={mac}):")
            for method, iurl in idds_candidates:
                try:
                    async with raw_session.request(method, iurl, json={}, headers=idds_h) as r:
                        body = await r.text()
                        ok = r.status not in (404, 405)
                        print(f"  {'✓ PATH EXISTS' if ok else '✗ '+str(r.status)+'  '}  {method} {iurl.replace(idds_base,'')}  → {r.status}: {body[:120]}")
                except Exception as e:
                    print(f"  ? ERROR  {method}  → {e}")

            # --- Part 0e: SignalR hub negotiate (confirmed reachable, needs GUC token) ---
            signalr_url = "https://signalr.globetools.systems:446/mowerSupport/negotiate?negotiateVersion=1"
            signalr_h = {**base_app_headers, "Authorization": f"Bearer {auth.guc_token}"}
            print(f"\n[0e] SignalR hub negotiate (signalr.globetools.systems:446/mowerSupport):")
            async with raw_session.post(signalr_url, headers=signalr_h) as resp:
                body = await resp.text()
                ok = resp.status in (200, 201)
                print(f"  {'✓ OK' if ok else '✗   '}  → {resp.status}: {body[:400]}")

            # --- Part 0d: device.globetools.systems (from HAR, held 60s connection) ---
            dev_h = {**base_app_headers, "Authorization": f"Bearer {auth.guc_token}"}
            dev_candidates = [
                ("GET",  f"{DEVICE_API_URL}/api/v1/device/{device_id}"),
                ("GET",  f"{DEVICE_API_URL}/api/v1/product/{product_id}/device/{device_id}"),
                ("POST", f"{DEVICE_API_URL}/api/v1/device/{device_id}/command"),
                ("POST", f"{DEVICE_API_URL}/api/v1/device/{device_id}/control"),
                ("POST", f"{DEVICE_API_URL}/api/device/{device_id}/dp-write"),
                ("POST", f"{DEVICE_API_URL}/v2/product/{product_id}/app_datapoint_value"),
            ]
            print(f"\n[0d] device.globetools.systems (HAR-discovered domain):")
            for method, durl in dev_candidates:
                try:
                    async with raw_session.request(method, durl, json={}, headers=dev_h) as resp:
                        body = await resp.text()
                        ok = resp.status not in (404, 405)
                        print(f"  {'✓ PATH EXISTS' if ok else '✗ '+str(resp.status)+'  '}  {method} {durl.replace(DEVICE_API_URL,'')}  → {resp.status}: {body[:100]}")
                except Exception as e:
                    print(f"  ✗ ERROR  {method}  → {e}")

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
