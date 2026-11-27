"""Config flow for Crema."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_URL
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_TOKEN, DEFAULT_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL, default=DEFAULT_URL): str,
        vol.Required(CONF_TOKEN): str,
    }
)


async def _async_validate(hass, url: str, token: str) -> str | None:
    """Return an error key, or None when the server answers with the token."""
    session = async_get_clientsession(hass)
    try:
        async with session.get(
            f"{url}/api/stats",
            headers={"Authorization": f"Bearer {token}"},
            timeout=aiohttp.ClientTimeout(total=15),
        ) as response:
            if response.status in (401, 403):
                return "invalid_auth"
            response.raise_for_status()
            await response.json()
            return None
    except TimeoutError:
        return "cannot_connect"
    except ValueError:
        return "invalid_response"
    except aiohttp.ClientError as err:
        _LOGGER.debug("Crema validation failed for %s: %s", url, err)
        return "cannot_connect"


class CremaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Ask for the server URL and the read-only token."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the single setup step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            url = user_input[CONF_URL].strip().rstrip("/")
            token = user_input[CONF_TOKEN].strip()

            await self.async_set_unique_id(url.lower())
            self._abort_if_unique_id_configured()

            error = await _async_validate(self.hass, url, token)
            if error:
                errors["base"] = error
            else:
                return self.async_create_entry(
                    title="Crema",
                    data={CONF_URL: url, CONF_TOKEN: token},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input or {}
            ),
            errors=errors,
        )
