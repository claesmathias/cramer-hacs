DOMAIN = "cramer_connect"

CONF_ORGANIZATION_ID = "organization_id"
CONF_PIN = "pin"

FLEET_API_URL = "https://cramerfleetapi.globetools.systems"
FLEET_AUTH_URL = "https://cramerfleetauth.globetools.systems"
XLINK_URL = "https://xapi.globetools.systems"
GUC_URL = "https://guc.globetools.systems:446"
DEVICE_API_URL = "https://device.globetools.systems"
PRODUCT_SERVICE_URL = "https://productservice.globetools.systems"

# MQTT broker used by the app to send commands to RLM1 mowers
# (APPconfig.BaseAddressMqttServer / BasePortMqttServer, TLS).
MQTT_HOST = "mqtt.globetools.systems"
MQTT_PORT = 1884
# The app publishes commands to "$7/<device_id>"
MQTT_COMMAND_TOPIC = "$7/{device_id}"

# GUC OAuth2 credentials — extracted from the Android app
GUC_CLIENT_ID = "CramerConnect"
GUC_CLIENT_SECRET = "351fc703-85f8-4fda-815a-6c2b1699b05a"
GUC_SCOPE = (
    "GlobeIotDashboardApi GimsSignalR IotDDSApi DeviceDbApi LicenseServiceApi "
    "PnmsCacheApi GfuApi openid offline_access profile GIotProductServiceApi "
    "GucApi ErrorServiceApi"
)
XLINK_CORP_ID = "100fa2b00b622800"

SCAN_INTERVAL_SECONDS = 30

# Required by the server — extracted from the Android app
APP_APPLICATION_KEY = "e4bc1f9c-6f1d-4349-b070-917a06dd05d8"
APP_BRAND = "Cramer"
APP_NAME = "Cramer Connect"

PRODUCT_CODE_RLM1 = "RLM1"
PRODUCT_CODE_RLM2 = "RLM2"
ROBOTIC_MOWER_PRODUCT_CODES = {PRODUCT_CODE_RLM1, PRODUCT_CODE_RLM2}

MOWER_STATE_MAP = {
    "0": "starting_up",
    "1": "stop_button_pressed",
    "2": "parked",
    "3": "paused",
    "4": "mowing",
    "5": "leaving_charging_station",
    "6": "searching_charging_station",
    "7": "charging",
    "8": "error",
    "9": "fatal_error",
    "10": "recovery_state",
    "11": "alarm_state",
    "12": "mowing_secondary_area",
}

# ---------------------------------------------------------------------------
# RLM1 MQTT command payloads (hex) — taken verbatim from RLM1HomeFragment.
# RLM2 mowers are controlled over (encrypted) Bluetooth only and cannot be
# commanded via the cloud.
# ---------------------------------------------------------------------------
# Start / resume mowing. When the mower's security level requires a PIN the
# last two bytes carry the PIN code (little-endian uint16).
CMD_START_PREFIX = "0007000d003a6000A007e400040000"
CMD_START = CMD_START_PREFIX + "0000"
# Stop (pause) the mower where it is.
CMD_STOP = "0007000b00386000A005e200020000"
# Park; followed by the park duration in minutes (little-endian uint16).
CMD_PARK_PREFIX = "0007000b003e6000A005e60002"
PARK_UNTIL_FURTHER_NOTICE = 0xFFFE  # "feff" on the wire
# Stop mowing the secondary area (used instead of CMD_STOP in state 12)
CMD_STOP_SECONDARY_AREA = "0007000c00366000A0064a0103000000"

# Weekly schedule (RLM1ScheduleFragment / ScheduleEditActivity): 7 days,
# Monday first, each day 2 timers of (hour, minute, length LE16, mode).
CMD_SCHEDULE_PREFIX = "0007004f00326000A049400146"
SCHEDULE_DAYS = (
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
)
SCHEDULE_TIMERS_PER_DAY = 2
# Nonstop mowing (ignore the schedule) for N minutes; all-zero cancels it
CMD_NONSTOP_PREFIX = "0007000c00366000A0064a0103"
CMD_NONSTOP_CANCEL = CMD_NONSTOP_PREFIX + "000000"
NONSTOP_MAX_DAYS = 24  # the app offers 1-24 days
# Set the mower clock: UTC epoch (LE32) + UTC offset in seconds (signed LE32)
CMD_SET_CLOCK_PREFIX = "0007001100566000A00b9a0008"
# source_for_next_start values meaning "nonstop mowing until next_start"
NONSTOP_SOURCES = {52, 53}

# Security levels (dp[8] response.security_level) that require a PIN
PIN_REQUIRED_SECURITY_LEVELS = {1, 9}

# DeviceStateBean.source_for_next_start → reason (meaningful in state 2/7)
NEXT_START_SOURCE_MAP = {
    1: "charging",
    2: "parked_by_schedule",
    3: "parked_max_day_cutting",
    4: "parked_by_user",
    5: "parked_by_rain_guard",
    6: "parked_by_frost_guard",
    7: "energy_saving_mode",
    52: "nonstop_mowing",
    53: "nonstop_mowing",
}

# State 2 (parked) is shown per reason, like the app does
PARKED_REASON_STATES = {
    1: "charging",
    2: "parked_by_schedule",
    3: "parked_max_day_cutting",
    4: "parked_by_user",
    5: "parked_by_rain_guard",
    6: "parked_by_frost_guard",
    7: "energy_saving_mode",
}

# All values the state sensor can take (SensorDeviceClass.ENUM options)
MOWER_STATE_OPTIONS = sorted(
    set(MOWER_STATE_MAP.values()) | set(PARKED_REASON_STATES.values())
)

# dp[33] request.event_id → error text (strings string_basefunction_mower_errorN)
MOWER_ERROR_MAP = {
    1: "Collision sensor failure.",
    2: "Collision sensor defect or mower is stuck.",
    3: "Front collision sensor defect or mower stuck when starting.",
    4: "Rear collision sensor defect or mower is stuck.",
    5: "Temporary lifted.",
    6: "Lift sensor defect. Unexpected signal from a lift sensor.",
    7: "Lift sensor defect or mower lifted.",
    8: "Front lift sensor defect or mower lifted when starting.",
    9: "Rear lift sensor defect or mower lifted when starting.",
    10: "Stop button defect.",
    11: "Safety key system error.",
    12: "Tilt sensor defect.",
    13: "Too high inclination.",
    14: "Mower is upside down.",
    15: "Too high current or voltage from PSU.",
    16: "No boundary signal detected when starting.",
    17: "Interference with other installation.",
    18: "Guide 1 not found.",
    19: "Guide 2 not found.",
    20: "Front right loop sensor defect.",
    21: "Front left loop sensor defect.",
    22: "Rear loop sensor defect.",
    23: "Communication problem with the charging station.",
    24: "No communication with communication module.",
    25: "No communication with GNSS-module.",
    26: "Weak GNSS signal.",
    27: "SIM card problem.",
    28: "Communication problem with cutting MCU.",
    29: "Internal error.",
    30: "Internal error.",
    31: "Internal error. Mower is reset to factory settings.",
    32: "Right wheel motor defective.",
    33: "Right wheel motor overloaded.",
    34: "Right wheel motor blocked.",
    35: "Right wheel motor drive system defect.",
    36: "Left wheel motor defective.",
    37: "Left wheel motor overloaded.",
    38: "Left wheel motor blocked.",
    39: "Left wheel motor drive system defect.",
    40: "Cutting motor defective.",
    41: "Cutting motor overloaded.",
    42: "Cutting motor blocked.",
    43: "Cutting motor drive system defect.",
    44: "Outside working area.",
    45: "The battery is not compatible with this mower.",
    46: "Battery communication problem.",
    47: "Battery empty.",
    48: "Battery temperature too high.",
    49: "Battery temperature too low.",
    50: "Battery over-voltage.",
    51: "Battery over-current.",
    52: "Mower has no drive.",
    53: "Mower is stuck.",
    54: "Charging station blocked. The mower cannot dock the charging station.",
    55: "Stuck in charging station.",
    56: "Main switch alarm. Mower turned off without PIN code.",
    57: "Lift sensor alarm. The mower is lifted.",
    58: "Geofence alarm. The mower is outside the geofence area.",
    59: "No boundary signal.",
    60: "Lost connection to charging station. Loop signal still detected.",
    61: "No power in charging station.",
    62: "Interference with loop signal from other installation. Change loop signal code.",
    63: "Mower software is updated.",
    64: "Mower started with safety key. Press STOP then START on mower.",
    65: "Front loop sensor defect.",
    66: "Cutting motor brake, defect.",
    67: "Too low charging current.",
    68: "Charging system defect in mower.",
    69: "Week timer enabled, but clock is not set.",
}
