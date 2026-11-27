"""Sensors for the Crema integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import CONF_URL, UnitOfMass, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import CremaConfigEntry, CremaCoordinator
from .const import DOMAIN


def _last_shot(data: dict[str, Any]) -> dict[str, Any]:
    return data.get("last_shot") or {}


def _best_shot(data: dict[str, Any]) -> dict[str, Any]:
    return data.get("best_shot") or {}


def _today_count(data: dict[str, Any]) -> int | None:
    series = data.get("series") or []
    return series[-1].get("count") if series else None


def _stamp(value: str | None) -> datetime | None:
    if not value:
        return None
    return dt_util.parse_datetime(value.replace("Z", "+00:00"))


def _last_attributes(data: dict[str, Any]) -> dict[str, Any]:
    shot = _last_shot(data)
    if not shot:
        return {}
    return {
        "shot_id": shot.get("id"),
        "bean": shot.get("bean_name"),
        "roaster": shot.get("bean_roaster"),
        "method": shot.get("method"),
        "rating": shot.get("rating"),
        "dose_g": shot.get("dose_g"),
        "yield_g": shot.get("yield_g"),
        "time_s": shot.get("time_s"),
        "grind": shot.get("grind"),
        "tasting_notes": shot.get("tasting_notes"),
        "is_cafe": shot.get("is_cafe"),
    }


def _best_attributes(data: dict[str, Any]) -> dict[str, Any]:
    shot = _best_shot(data)
    if not shot:
        return {}
    return {
        "shot_id": shot.get("id"),
        "bean": shot.get("bean_name"),
        "roaster": shot.get("bean_roaster"),
        "method": shot.get("method"),
        "brewed_at": shot.get("brewed_at"),
    }


def _favorite_attributes(data: dict[str, Any]) -> dict[str, Any]:
    bean = data.get("favorite_bean") or {}
    return {"roaster": bean.get("roaster"), "shots": bean.get("count")}


@dataclass(frozen=True, kw_only=True)
class CremaSensorEntityDescription(SensorEntityDescription):
    """A Crema sensor, with a function that pulls its value out of the payload."""

    value_fn: Callable[[dict[str, Any]], Any]
    attrs_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None


SENSORS: tuple[CremaSensorEntityDescription, ...] = (
    CremaSensorEntityDescription(
        key="total_shots",
        name="Total shots",
        icon="mdi:coffee",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.get("total_shots"),
    ),
    CremaSensorEntityDescription(
        key="week_shots",
        name="Shots this week",
        icon="mdi:calendar-week",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.get("week_shots"),
    ),
    CremaSensorEntityDescription(
        key="today_shots",
        name="Shots today",
        icon="mdi:calendar-today",
        state_class=SensorStateClass.TOTAL,
        value_fn=_today_count,
    ),
    CremaSensorEntityDescription(
        key="cafe_shots",
        name="Café visits",
        icon="mdi:storefront-outline",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.get("cafe_shots"),
    ),
    CremaSensorEntityDescription(
        key="avg_rating",
        name="Average rating",
        icon="mdi:star-outline",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda data: data.get("avg_rating"),
    ),
    CremaSensorEntityDescription(
        key="best_rating",
        name="Best rating",
        icon="mdi:star",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: _best_shot(data).get("rating"),
        attrs_fn=_best_attributes,
    ),
    CremaSensorEntityDescription(
        key="avg_dose",
        name="Average dose",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.GRAMS,
        suggested_display_precision=1,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("avg_dose"),
    ),
    CremaSensorEntityDescription(
        key="avg_yield",
        name="Average yield",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.GRAMS,
        suggested_display_precision=1,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("avg_yield"),
    ),
    CremaSensorEntityDescription(
        key="avg_time",
        name="Average shot time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("avg_time"),
    ),
    CremaSensorEntityDescription(
        key="bean_count",
        name="Beans in stock",
        icon="mdi:seed-outline",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.get("bean_count"),
    ),
    CremaSensorEntityDescription(
        key="favorite_bean",
        name="Favourite bean",
        icon="mdi:heart-outline",
        value_fn=lambda data: (data.get("favorite_bean") or {}).get("name"),
        attrs_fn=_favorite_attributes,
    ),
    CremaSensorEntityDescription(
        key="last_shot",
        name="Last shot",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: _stamp(_last_shot(data).get("brewed_at")),
        attrs_fn=_last_attributes,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CremaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Crema sensors."""
    coordinator = entry.runtime_data
    async_add_entities(CremaSensor(coordinator, description) for description in SENSORS)


class CremaSensor(CoordinatorEntity[CremaCoordinator], SensorEntity):
    """One number (or timestamp) out of the Crema stats payload."""

    _attr_has_entity_name = True
    entity_description: CremaSensorEntityDescription

    def __init__(
        self,
        coordinator: CremaCoordinator,
        description: CremaSensorEntityDescription,
    ) -> None:
        """Set up the sensor from its description."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name="Crema",
            manufacturer="Crema",
            model="Coffee journal",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=coordinator.config_entry.data[CONF_URL],
        )

    @property
    def native_value(self) -> Any:
        """Return the value for this sensor."""
        return self.entity_description.value_fn(self.coordinator.data or {})

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the shot (or bean) details behind the value."""
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self.coordinator.data or {})
