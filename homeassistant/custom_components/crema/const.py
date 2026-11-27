"""Constants for the Crema integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "crema"

CONF_TOKEN = "token"

DEFAULT_URL = "http://10.0.1.15:8787"
DEFAULT_SCAN_INTERVAL = timedelta(minutes=5)
