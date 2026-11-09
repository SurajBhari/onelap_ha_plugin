"""Config flow for the Onelap integration."""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import parse_qs, urlparse

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
    ConfigEntry,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import OnelapApiClient, OnelapApiError, OnelapAuthError
from .const import (
    CONF_SCAN_INTERVAL,
    CONF_TRACKING_ID,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


def _extract_tracking_id(raw: str) -> str:
    """Accept either a bare tracking id or a full share URL.

    Examples handled::

        XXXXXX
        https://r.onelap.in/#/shared?tid=XXXXXX
        https://r.onelap.in/#/shared?tid=XXXXXX&foo=bar
    """
    raw = raw.strip()
    if "tid=" in raw:
        # The tid lives in the fragment for the Flutter app's hash router,
        # so parse it out directly rather than relying on urlparse.query.
        match = re.search(r"tid=([^&\s]+)", raw)
        if match:
            return match.group(1)
        # Fallback: standard query string.
        parsed = urlparse(raw)
        qs = parse_qs(parsed.query)
        if "tid" in qs:
            return qs["tid"][0]
    return raw


class OnelapConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Onelap."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            tracking_id = _extract_tracking_id(user_input[CONF_TRACKING_ID])
            await self.async_set_unique_id(tracking_id)
            self._abort_if_unique_id_configured()

            session = async_get_clientsession(self.hass)
            client = OnelapApiClient(tracking_id, session)
            try:
                devices = await client.async_validate()
            except OnelapAuthError:
                errors["base"] = "invalid_tracking_id"
            except OnelapApiError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error validating Onelap share link")
                errors["base"] = "unknown"
            else:
                # Name the entry after the first vehicle, if available.
                first = devices[0]
                attrs = first.get("attributes") or {}
                title = (
                    attrs.get("vehicleNumber")
                    or first.get("name")
                    or f"Onelap {tracking_id}"
                )
                return self.async_create_entry(
                    title=str(title),
                    data={CONF_TRACKING_ID: tracking_id},
                )

        schema = vol.Schema({vol.Required(CONF_TRACKING_ID): str})
        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OnelapOptionsFlow:
        return OnelapOptionsFlow()


class OnelapOptionsFlow(OptionsFlow):
    """Handle Onelap options (polling interval)."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        schema = vol.Schema(
            {
                vol.Required(CONF_SCAN_INTERVAL, default=current): vol.All(
                    vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=3600)
                )
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
