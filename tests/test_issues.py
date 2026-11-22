"""Repair issues for lost connections (Settings → System → Repairs)."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.cramer_connect import issues as issues_mod
from custom_components.cramer_connect.api import CramerDevice
from custom_components.cramer_connect.coordinator import CramerConnectCoordinator
from custom_components.cramer_connect.issues import ConnectionIssues

T0 = datetime(2026, 11, 22, 10, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _reset_registry():
    ir.async_create_issue.reset_mock()
    ir.async_delete_issue.reset_mock()


class _Clock:
    def __init__(self):
        self.now = T0

    def __call__(self):
        return self.now


@pytest.fixture
def clock():
    c = _Clock()
    with patch.object(issues_mod.dt_util, "utcnow", c):
        yield c


def _mower(online=True, device_id="1"):
    return CramerDevice(device_id, "p", "Nacho", "", "", "RLM1", "4", 50, online)


class TestCloudUnreachable:
    def test_no_issue_for_short_outage(self, clock):
        iss = ConnectionIssues(MagicMock(), "entry")
        iss.cloud_failed("timeout")
        clock.now = T0 + timedelta(minutes=10)
        iss.cloud_failed("timeout")
        ir.async_create_issue.assert_not_called()

    def test_issue_after_grace(self, clock):
        iss = ConnectionIssues(MagicMock(), "entry")
        iss.cloud_failed("timeout")
        clock.now = T0 + timedelta(minutes=16)
        iss.cloud_failed("HTTP 503")
        call = ir.async_create_issue.call_args
        assert call.args[2] == "cloud_unreachable_entry"
        assert call.kwargs["translation_placeholders"]["error"] == "HTTP 503"

    def test_success_resets_and_clears(self, clock):
        iss = ConnectionIssues(MagicMock(), "entry")
        iss.cloud_failed("timeout")
        clock.now = T0 + timedelta(minutes=16)
        iss.cloud_failed("timeout")
        iss.cloud_ok()
        ir.async_delete_issue.assert_called_with(iss._hass, "cramer_connect", "cloud_unreachable_entry")
        ir.async_create_issue.reset_mock()
        clock.now = T0 + timedelta(minutes=20)
        iss.cloud_failed("timeout")  # new outage starts a new grace period
        ir.async_create_issue.assert_not_called()

    def test_clear_all_on_unload(self, clock):
        iss = ConnectionIssues(MagicMock(), "entry")
        iss.clear_all()
        ir.async_delete_issue.assert_called_with(iss._hass, "cramer_connect", "cloud_unreachable_entry")


class TestCoordinatorWiring:
    def _coord(self):
        coord = CramerConnectCoordinator.__new__(CramerConnectCoordinator)
        coord.issues = MagicMock()
        return coord

    async def test_failure_reported_to_issues(self):
        coord = self._coord()
        coord._async_fetch = AsyncMock(side_effect=UpdateFailed("HTTP 503"))
        with pytest.raises(UpdateFailed):
            await coord._async_update_data()
        coord.issues.cloud_failed.assert_called_once_with("HTTP 503")
        coord.issues.cloud_ok.assert_not_called()

    async def test_success_clears_issue(self):
        coord = self._coord()
        data = {"1": _mower(online=False)}
        coord._async_fetch = AsyncMock(return_value=data)
        assert await coord._async_update_data() == data
        coord.issues.cloud_ok.assert_called_once()

    def test_offline_mower_creates_no_issue(self):
        from custom_components.cramer_connect.issues import ConnectionIssues as CI
        assert not hasattr(CI, "update_devices")


def test_issue_translations_exist():
    strings = json.loads((Path(__file__).parent.parent / "custom_components/cramer_connect/strings.json").read_text())
    assert set(strings["issues"]) == {"cloud_unreachable"}
    for key, placeholders in (("cloud_unreachable", ["{since}", "{error}"]),):
        text = strings["issues"][key]["title"] + strings["issues"][key]["description"]
        for ph in placeholders:
            assert ph in text
