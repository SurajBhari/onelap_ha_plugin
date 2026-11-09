"""Thin async client for the Onelap public tracking API.

Onelap exposes a small set of *public* (no-auth) endpoints that back the
share page at ``https://r.onelap.in/#/shared?tid=<trackingId>``. Given only
the tracking id from a share link we can list the shared devices and fetch
each device's latest GPS position. That is everything this integration needs.

Discovered endpoints (base ``https://web.onelap.in``)::

    GET /api/trackingPermission/public-devices?trackingId=<tid>
        -> [ { id, name, uniqueId, status, lastUpdate, attributes{...} } ]

    GET /api/positions/latest/public?trackingId=<tid>&deviceId=<id>
        -> { latitude, longitude, speed, course, fixTime, attributes{...}, ... }

The ``speed`` field follows the Traccar convention (knots); callers convert.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://web.onelap.in"
REQUEST_TIMEOUT = 20


class OnelapApiError(Exception):
    """Raised when the Onelap API cannot be reached or returns an error."""


class OnelapAuthError(OnelapApiError):
    """Raised when the tracking id is invalid / shares no devices."""


class OnelapApiClient:
    """Minimal client for the Onelap public share endpoints."""

    def __init__(
        self,
        tracking_id: str,
        session: aiohttp.ClientSession,
        base_url: str = DEFAULT_BASE_URL,
    ) -> None:
        self._tracking_id = tracking_id.strip()
        self._session = session
        self._base_url = base_url.rstrip("/")

    @property
    def tracking_id(self) -> str:
        return self._tracking_id

    async def _get(self, path: str, params: dict[str, Any]) -> Any:
        url = f"{self._base_url}{path}"
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                resp = await self._session.get(
                    url,
                    params=params,
                    headers={
                        "Accept": "application/json",
                        # The share page is a browser app; be a good citizen.
                        "Referer": "https://r.onelap.in/",
                        "X-Requested-With": "XMLHttpRequest",
                    },
                )
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise OnelapApiError(f"Error talking to Onelap: {err}") from err

        if resp.status == 204:
            return None
        if resp.status in (401, 403):
            raise OnelapAuthError(
                f"Tracking id rejected by Onelap (HTTP {resp.status})"
            )
        if resp.status >= 400:
            text = await resp.text()
            raise OnelapApiError(
                f"Onelap GET {path} failed (HTTP {resp.status}): {text[:200]}"
            )

        try:
            return await resp.json(content_type=None)
        except (aiohttp.ContentTypeError, ValueError) as err:
            raise OnelapApiError(f"Onelap returned non-JSON for {path}") from err

    async def async_get_devices(self) -> list[dict[str, Any]]:
        """Return the list of devices shared under this tracking id."""
        data = await self._get(
            "/api/trackingPermission/public-devices",
            {"trackingId": self._tracking_id},
        )
        if not isinstance(data, list):
            raise OnelapAuthError(
                "Onelap returned no devices for this tracking id. "
                "Check that the share link is correct and still active."
            )
        return data

    async def async_get_position(self, device_id: int) -> dict[str, Any] | None:
        """Return the latest position for a device, or ``None`` if unknown."""
        data = await self._get(
            "/api/positions/latest/public",
            {"trackingId": self._tracking_id, "deviceId": device_id},
        )
        if data is None:
            return None
        # Some deployments return a single object; others a one-item list.
        if isinstance(data, list):
            return data[0] if data else None
        if isinstance(data, dict):
            return data
        return None

    async def async_validate(self) -> list[dict[str, Any]]:
        """Validate the tracking id during config flow. Returns the devices."""
        devices = await self.async_get_devices()
        if not devices:
            raise OnelapAuthError("This Onelap share link exposes no devices.")
        return devices
