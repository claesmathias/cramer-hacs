"""Connection problem shown under Settings → System → Repairs.

cloud_unreachable: Home Assistant could not reach the Cramer servers for
CLOUD_UNREACHABLE_GRACE. Cleared automatically once they respond again.

A mower being offline is deliberately not reported here: mowers are often
switched off for the winter, which would leave a permanent message. The
Online sensor and the Status sensor show that instead. A refused password is
handled by Home Assistant's re-authentication flow.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util

from .const import DOMAIN

# Short cloud hiccups are normal
CLOUD_UNREACHABLE_GRACE = timedelta(minutes=15)

ISSUE_CLOUD_UNREACHABLE = "cloud_unreachable"


class ConnectionIssues:
    """Raise and clear the 'Cramer servers unreachable' issue for one entry."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._hass = hass
        self._entry_id = entry_id
        self._failing_since: datetime | None = None

    @property
    def _issue_id(self) -> str:
        return f"{ISSUE_CLOUD_UNREACHABLE}_{self._entry_id}"

    def cloud_failed(self, error: str) -> None:
        now = dt_util.utcnow()
        if self._failing_since is None:
            self._failing_since = now
        if now - self._failing_since < CLOUD_UNREACHABLE_GRACE:
            return
        ir.async_create_issue(
            self._hass,
            DOMAIN,
            self._issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=ISSUE_CLOUD_UNREACHABLE,
            translation_placeholders={
                "since": dt_util.as_local(self._failing_since).strftime("%Y-%m-%d %H:%M"),
                "error": error[:200] or "unknown error",
            },
        )

    def cloud_ok(self) -> None:
        # Always delete (a no-op when absent): an issue can outlive a restart
        self._failing_since = None
        ir.async_delete_issue(self._hass, DOMAIN, self._issue_id)

    def clear_all(self) -> None:
        """Remove the issue of this entry (on unload)."""
        self.cloud_ok()
