"""Live integration test for the Cramer Connect login flow.

Run with:
    pytest tests/test_login_live.py -v -s --password YOUR_PASSWORD

Or via environment variable:
    CRAMER_PASSWORD=YOUR_PASSWORD pytest tests/test_login_live.py -v -s
"""
import os

import aiohttp
import pytest

USERNAME = "claesmathias@gmail.com"



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
    async def test_login_returns_tokens(self, client, password):
        auth = await client.authenticate(USERNAME, password)

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

    async def test_devices_listed_after_login(self, client, password):
        auth = await client.authenticate(USERNAME, password)
        devices = await client.get_devices(auth)

        print(f"\nFound {len(devices)} device(s):")
        for d in devices:
            print(f"  [{d.product_code}] {d.name!r}  state={d.state_label}  battery={d.battery}%  online={d.is_online}")

        assert isinstance(devices, list), "get_devices should return a list"
