"""The Onelap vehicle tracking integration."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import OnelapApiClient
from .const import (
    CONF_SCAN_INTERVAL,
    CONF_TRACKING_ID,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
)
from .coordinator import OnelapDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.DEVICE_TRACKER,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
]

type OnelapConfigEntry = ConfigEntry[OnelapDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: OnelapConfigEntry) -> bool:
    """Set up Onelap from a config entry."""
    tracking_id = entry.data[CONF_TRACKING_ID]
    session = async_get_clientsession(hass)
    client = OnelapApiClient(tracking_id, session)

    scan_interval = max(
        MIN_SCAN_INTERVAL,
        entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
    )
    coordinator = OnelapDataUpdateCoordinator(
        hass, entry, client, timedelta(seconds=scan_interval)
    )

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: OnelapConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(
    hass: HomeAssistant, entry: OnelapConfigEntry
) -> None:
    """Reload the entry when options (e.g. scan interval) change."""
    await hass.config_entries.async_reload(entry.entry_id)
