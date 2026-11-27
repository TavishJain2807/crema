"""The Crema integration: coffee stats from a self-hosted Crema server."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_TOKEN, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

type CremaConfigEntry = ConfigEntry[CremaCoordinator]


class CremaCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll the Crema stats endpoint with the read-only token."""

    config_entry: CremaConfigEntry

    def __init__(self, hass: HomeAssistant, entry: CremaConfigEntry) -> None:
        """Set up the coordinator from the config entry."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self._url = entry.data[CONF_URL].rstrip("/")
        self._token = entry.data[CONF_TOKEN]

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch the current stats."""
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(
                f"{self._url}/api/stats",
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as response:
                if response.status in (401, 403):
                    raise UpdateFailed("Crema rejected the read token")
                response.raise_for_status()
                return await response.json()
        except TimeoutError as err:
            raise UpdateFailed("Timed out talking to Crema") from err
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error talking to Crema: {err}") from err


async def async_setup_entry(hass: HomeAssistant, entry: CremaConfigEntry) -> bool:
    """Set up Crema from a config entry."""
    coordinator = CremaCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: CremaConfigEntry) -> bool:
    """Unload a Crema config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
