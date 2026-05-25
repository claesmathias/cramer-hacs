DOMAIN = "cramer_connect"

CONF_ORGANIZATION_ID = "organization_id"

FLEET_API_URL = "https://cramerfleetapi.globetools.systems"
FLEET_AUTH_URL = "https://cramerfleetauth.globetools.systems"

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
