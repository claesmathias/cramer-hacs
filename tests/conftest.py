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


_const.Platform = _Platform


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


_exc.ConfigEntryAuthFailed = _ConfigEntryAuthFailed
_exc.ConfigEntryNotReady = _ConfigEntryNotReady

# ---- homeassistant.config_entries ------------------------------------------
_ce = _module("homeassistant.config_entries")
_ce.ConfigEntry = type("ConfigEntry", (), {})
_ce.ConfigFlow = type("ConfigFlow", (), {"async_set_unique_id": MagicMock(), "_abort_if_unique_id_configured": MagicMock()})

# ---- homeassistant.core ----------------------------------------------------
_core = _module("homeassistant.core")
_core.HomeAssistant = type("HomeAssistant", (), {})

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
    {"BATTERY": "battery", "DURATION": "duration", "TIMESTAMP": "timestamp"},
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
    {"CONNECTIVITY": "connectivity", "UPDATE": "update"},
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

# ---- homeassistant.data_entry_flow -----------------------------------------
_flow = _module("homeassistant.data_entry_flow")
_flow.FlowResult = dict

# ---- voluptuous (used in config_flow) --------------------------------------
try:
    import voluptuous  # noqa: F401
except ImportError:
    _vol = _module("voluptuous")
    _vol.Schema = lambda x: x
    _vol.Required = lambda k: k
