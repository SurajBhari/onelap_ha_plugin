"""Constants for the Onelap integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "onelap"

CONF_TRACKING_ID = "tracking_id"

# Config / options keys
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_SCAN_INTERVAL = 30  # seconds
MIN_SCAN_INTERVAL = 10
DEFAULT_UPDATE_INTERVAL = timedelta(seconds=DEFAULT_SCAN_INTERVAL)

MANUFACTURER = "Onelap Telematics"

# Knots -> km/h (Traccar stores speed in knots).
KNOTS_TO_KMPH = 1.852

ATTR_TRACKING_ID = "tracking_id"
