"""Constants for the ESTOFEX integration."""

DOMAIN = "estofex"

BASE_URL = "https://www.estofex.org/cgi-bin/polygon/showforecast.cgi"
DEFAULT_SCAN_INTERVAL_HOURS = 1

EVENT_FORECAST_UPDATED = "estofex_forecast_updated"
EVENT_WARNING_STARTED = "estofex_warning_started"
EVENT_WARNING_CLEARED = "estofex_warning_cleared"

WWW_DIR = "www/estofex"
LATEST_IMAGE_FILENAME = "latest.png"
