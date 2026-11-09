"""DataUpdateCoordinator for the Onelap integration."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import OnelapApiClient, OnelapApiError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class OnelapDevice:
    """Merged device metadata + latest position for a single tracker."""

    id: int
    name: str
    unique_id: str
    status: str | None = None
    last_update: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    position: dict[str, Any] | None = None

    @property
    def vehicle_number(self) -> str | None:
        value = self.attributes.get("vehicleNumber")
        return str(value) if value else None

    @property
    def latitude(self) -> float | None:
        if self.position is None:
            return None
        lat = self.position.get("latitude")
        return float(lat) if isinstance(lat, (int, float)) else None

    @property
    def longitude(self) -> float | None:
        if self.position is None:
            return None
        lon = self.position.get("longitude")
        return float(lon) if isinstance(lon, (int, float)) else None

    @property
    def has_fix(self) -> bool:
        lat, lon = self.latitude, self.longitude
        # 0,0 ("null island") means the device has never reported a real fix.
        return lat is not None and lon is not None and (lat != 0 or lon != 0)


class OnelapDataUpdateCoordinator(DataUpdateCoordinator[dict[int, OnelapDevice]]):
    """Polls the Onelap public API and exposes devices keyed by device id."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: OnelapApiClient,
        update_interval: timedelta,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} ({client.tracking_id})",
            update_interval=update_interval,
        )
        self.entry = entry
        self.client = client

    async def _async_update_data(self) -> dict[int, OnelapDevice]:
        try:
            raw_devices = await self.client.async_get_devices()
        except OnelapApiError as err:
            raise UpdateFailed(str(err)) from err

        devices: dict[int, OnelapDevice] = {}
        for raw in raw_devices:
            dev_id = raw.get("id")
            if dev_id is None:
                continue
            devices[dev_id] = OnelapDevice(
                id=dev_id,
                name=(raw.get("name") or f"Onelap {dev_id}").strip(),
                unique_id=str(raw.get("uniqueId") or dev_id),
                status=raw.get("status"),
                last_update=raw.get("lastUpdate"),
                attributes=raw.get("attributes") or {},
            )

        # Fetch latest positions concurrently.
        async def _fill_position(device: OnelapDevice) -> None:
            try:
                device.position = await self.client.async_get_position(device.id)
            except OnelapApiError as err:
                _LOGGER.debug("No position for device %s: %s", device.id, err)
                device.position = None

        await asyncio.gather(*(_fill_position(d) for d in devices.values()))
        return devices
