"""Inject homeassistant stubs before any test module is imported."""


def pytest_addoption(parser):
    parser.addoption("--username", action="store", default=None, help="Cramer Connect username (email)")
    parser.addoption("--password", action="store", default=None, help="Cramer Connect password")
import sys
import types
from enum import Enum
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _module(name: str) -> types.ModuleType:
    m = types.ModuleType(name)
    sys.modules[name] = m
    return m


# ---- homeassistant.const ---------------------------------------------------
_const = _module("homeassistant.const")
_const.CONF_USERNAME = "username"
_const.CONF_PASSWORD = "password"
_const.PERCENTAGE = "%"


class _Platform(str, Enum):
    SENSOR = "sensor"
    BINARY_SENSOR = "binary_sensor"
    DEVICE_TRACKER = "device_tracker"
    BUTTON = "button"
    LAWN_MOWER = "lawn_mower"
    UPDATE = "update"
    CALENDAR = "calendar"


_const.Platform = _Platform


class _EntityCategory(str, Enum):
    CONFIG = "config"
    DIAGNOSTIC = "diagnostic"


_const.EntityCategory = _EntityCategory


class _UnitOfTime:
    SECONDS = "s"
    MINUTES = "min"
    HOURS = "h"


_const.UnitOfTime = _UnitOfTime


class _UnitOfLength:
    METERS = "m"
    KILOMETERS = "km"
    MILES = "mi"


_const.UnitOfLength = _UnitOfLength

# ---- homeassistant.exceptions ----------------------------------------------
_exc = _module("homeassistant.exceptions")


class _ConfigEntryAuthFailed(Exception):
    pass


class _ConfigEntryNotReady(Exception):
    pass


class _HomeAssistantError(Exception):
    pass


_exc.HomeAssistantError = _HomeAssistantError
_exc.ConfigEntryAuthFailed = _ConfigEntryAuthFailed
_exc.ConfigEntryNotReady = _ConfigEntryNotReady

# ---- homeassistant.config_entries ------------------------------------------
_ce = _module("homeassistant.config_entries")
_ce.ConfigEntry = type("ConfigEntry", (), {})
_ce.ConfigFlow = type("ConfigFlow", (), {"async_set_unique_id": MagicMock(), "_abort_if_unique_id_configured": MagicMock()})
_ce.OptionsFlow = type("OptionsFlow", (), {})

# ---- homeassistant.core ----------------------------------------------------
_core = _module("homeassistant.core")
_core.HomeAssistant = type("HomeAssistant", (), {})
_core.callback = lambda f: f

# ---- homeassistant.util ----------------------------------------------------
_util = _module("homeassistant.util")
_util_dt = _module("homeassistant.util.dt")
from datetime import datetime as _datetime
_util_dt.now = lambda: _datetime.now().astimezone()
_util_dt.as_local = lambda d: d.astimezone()
from zoneinfo import ZoneInfo as _ZoneInfo
_util_dt.get_default_time_zone = lambda: _ZoneInfo("Europe/Brussels")
_util.dt = _util_dt
_util_ssl = _module("homeassistant.util.ssl")
_util_ssl.get_default_context = MagicMock()

# ---- homeassistant.helpers -------------------------------------------------
_helpers = _module("homeassistant.helpers")

_aio = _module("homeassistant.helpers.aiohttp_client")
_aio.async_get_clientsession = MagicMock()

_coord = _module("homeassistant.helpers.update_coordinator")
_coord.DataUpdateCoordinator = type(
    "DataUpdateCoordinator",
    (),
    {
        "__init_subclass__": classmethod(lambda cls, **kw: None),
        "__class_getitem__": classmethod(lambda cls, item: cls),
    },
)
_coord.UpdateFailed = type("UpdateFailed", (Exception,), {})

_ep = _module("homeassistant.helpers.entity_platform")
_ep.AddEntitiesCallback = None
_ep.async_get_current_platform = MagicMock()
_helpers.entity_platform = _ep

_er = _module("homeassistant.helpers.entity_registry")
_er.async_get = MagicMock()
_helpers.entity_registry = _er

_cv = _module("homeassistant.helpers.config_validation")
_cv.positive_int = int
_cv.ensure_list = lambda v: v if isinstance(v, list) else [v]
_cv.time = lambda v: v
_helpers.config_validation = _cv

_dr = _module("homeassistant.helpers.device_registry")
_dr.DeviceInfo = dict  # DeviceInfo is TypedDict-like; dict is close enough for tests

_ent = _module("homeassistant.helpers.entity")
_ent.DeviceInfo = dict

_ucoord = _module("homeassistant.helpers.update_coordinator")
def _ce_init(self, coordinator):
    self.coordinator = coordinator

_ucoord.CoordinatorEntity = type("CoordinatorEntity", (), {
    "__init__": _ce_init,
    "__class_getitem__": classmethod(lambda cls, item: cls),
})
_ucoord.DataUpdateCoordinator = type("DataUpdateCoordinator", (), {
    "__init_subclass__": classmethod(lambda cls, **kw: None),
    "__class_getitem__": classmethod(lambda cls, item: cls),
})
_ucoord.UpdateFailed = type("UpdateFailed", (Exception,), {})

# ---- homeassistant.components.sensor ---------------------------------------
_sensor_mod = _module("homeassistant.components.sensor")
_sensor_mod.SensorEntity = type("SensorEntity", (), {})
_sensor_mod.SensorDeviceClass = type(
    "SensorDeviceClass", (),
    {"BATTERY": "battery", "DURATION": "duration", "TIMESTAMP": "timestamp",
     "ENUM": "enum", "DISTANCE": "distance"},
)
_sensor_mod.SensorStateClass = type(
    "SensorStateClass", (),
    {"MEASUREMENT": "measurement", "TOTAL_INCREASING": "total_increasing"},
)
def _sed_init(self, **kw):
    self.__dict__.update(kw)
    self.__dict__.setdefault("suggested_display_precision", None)

_sensor_mod.SensorEntityDescription = type(
    "SensorEntityDescription",
    (),
    {"__init__": _sed_init},
)

# ---- homeassistant.components.binary_sensor --------------------------------
_bs_mod = _module("homeassistant.components.binary_sensor")
_bs_mod.BinarySensorEntity = type("BinarySensorEntity", (), {})
_bs_mod.BinarySensorDeviceClass = type(
    "BinarySensorDeviceClass", (),
    {"CONNECTIVITY": "connectivity", "UPDATE": "update",
     "BATTERY_CHARGING": "battery_charging"},
)

# ---- homeassistant.components.device_tracker --------------------------------
_dt_mod = _module("homeassistant.components.device_tracker")
_dt_mod.TrackerEntity = type("TrackerEntity", (), {})


class _SourceType(str):
    pass


_dt_mod.SourceType = type(
    "SourceType",
    (),
    {"GPS": _SourceType("gps"), "ROUTER": _SourceType("router")},
)

# ---- homeassistant.components.button ----------------------------------------
_btn_mod = _module("homeassistant.components.button")
_btn_mod.ButtonEntity = type("ButtonEntity", (), {})

# ---- homeassistant.components.lawn_mower ------------------------------------
_lm_mod = _module("homeassistant.components.lawn_mower")
_lm_mod.LawnMowerEntity = type("LawnMowerEntity", (), {})


class _LawnMowerActivity(str, Enum):
    ERROR = "error"
    PAUSED = "paused"
    MOWING = "mowing"
    DOCKED = "docked"
    RETURNING = "returning"


class _LawnMowerEntityFeature:
    START_MOWING = 1
    PAUSE = 2
    DOCK = 4


_lm_mod.LawnMowerActivity = _LawnMowerActivity
_lm_mod.LawnMowerEntityFeature = _LawnMowerEntityFeature

# ---- homeassistant.components.calendar ---------------------------------------
from dataclasses import dataclass as _dataclass
_cal_mod = _module("homeassistant.components.calendar")
_cal_mod.CalendarEntity = type("CalendarEntity", (), {})


@_dataclass
class _CalendarEvent:
    start: object
    end: object
    summary: str
    description: str | None = None


_cal_mod.CalendarEvent = _CalendarEvent

# ---- homeassistant.components.update -----------------------------------------
_upd_mod = _module("homeassistant.components.update")
_upd_mod.UpdateEntity = type("UpdateEntity", (), {})
_upd_mod.UpdateDeviceClass = type("UpdateDeviceClass", (), {"FIRMWARE": "firmware"})

# ---- homeassistant.components.diagnostics -------------------------------------
_diag_mod = _module("homeassistant.components.diagnostics")


def _redact(data, to_redact):
    if isinstance(data, list):
        return [_redact(v, to_redact) for v in data]
    if not isinstance(data, dict):
        return data
    return {
        k: ("**REDACTED**" if k in to_redact else _redact(v, to_redact))
        for k, v in data.items()
    }


_diag_mod.async_redact_data = _redact

# ---- homeassistant.data_entry_flow -----------------------------------------
_flow = _module("homeassistant.data_entry_flow")
_flow.FlowResult = dict

# ---- voluptuous (used in config_flow) --------------------------------------
try:
    import voluptuous  # noqa: F401
except ImportError:
    _vol = _module("voluptuous")
    _vol.Schema = lambda x: x
    _vol.Required = lambda k, **kw: k
    _vol.Optional = lambda k, **kw: k
    _vol.All = lambda *a: a
    _vol.In = lambda x: x
    _vol.Coerce = lambda t: t
    _vol.Range = lambda **kw: kw
