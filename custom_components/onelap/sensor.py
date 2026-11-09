"""Sensor platform for Onelap — speed, direction, ignition, status, etc."""

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
from homeassistant.const import (
    DEGREE,
    UnitOfLength,
    UnitOfSpeed,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import OnelapConfigEntry
from .const import KNOTS_TO_KMPH
from .coordinator import OnelapDataUpdateCoordinator, OnelapDevice
from .entity import OnelapEntity


def _pos_attr(device: OnelapDevice, key: str) -> Any:
    pos = device.position or {}
    return (pos.get("attributes") or {}).get(key)


def _speed_kmph(device: OnelapDevice) -> float | None:
    pos = device.position or {}
    speed = pos.get("speed")
    if isinstance(speed, (int, float)):
        return round(speed * KNOTS_TO_KMPH, 1)
    return None


def _course(device: OnelapDevice) -> float | None:
    pos = device.position or {}
    course = pos.get("course")
    return float(course) if isinstance(course, (int, float)) else None


def _total_distance_km(device: OnelapDevice) -> float | None:
    val = _pos_attr(device, "totalDistance")
    return round(float(val) / 1000, 2) if isinstance(val, (int, float)) else None


def _last_fix(device: OnelapDevice) -> datetime | None:
    pos = device.position or {}
    raw = pos.get("fixTime") or device.last_update
    if not raw:
        return None
    return dt_util.parse_datetime(raw)


@dataclass(frozen=True, kw_only=True)
class OnelapSensorDescription(SensorEntityDescription):
    """Describes an Onelap sensor and how to read its value."""

    value_fn: Callable[[OnelapDevice], Any]


SENSORS: tuple[OnelapSensorDescription, ...] = (
    OnelapSensorDescription(
        key="speed",
        translation_key="speed",
        icon="mdi:speedometer",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_speed_kmph,
    ),
    OnelapSensorDescription(
        key="course",
        translation_key="course",
        icon="mdi:compass",
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_course,
    ),
    OnelapSensorDescription(
        key="status",
        translation_key="status",
        icon="mdi:car-connected",
        value_fn=lambda d: d.status,
    ),
    OnelapSensorDescription(
        key="satellites",
        translation_key="satellites",
        icon="mdi:satellite-variant",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: _pos_attr(d, "sat"),
    ),
    OnelapSensorDescription(
        key="total_distance",
        translation_key="total_distance",
        icon="mdi:map-marker-distance",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=_total_distance_km,
    ),
    OnelapSensorDescription(
        key="last_fix",
        translation_key="last_fix",
        icon="mdi:clock-outline",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_last_fix,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OnelapConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Onelap sensors."""
    coordinator = entry.runtime_data
    known: set[int] = set()

    @callback
    def _add_new_devices() -> None:
        new: list[OnelapSensor] = []
        for device_id in coordinator.data:
            if device_id in known:
                continue
            known.add(device_id)
            new.extend(
                OnelapSensor(coordinator, device_id, desc) for desc in SENSORS
            )
        if new:
            async_add_entities(new)

    _add_new_devices()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_devices))


class OnelapSensor(OnelapEntity, SensorEntity):
    """A single Onelap-derived sensor."""

    entity_description: OnelapSensorDescription

    def __init__(
        self,
        coordinator: OnelapDataUpdateCoordinator,
        device_id: int,
        description: OnelapSensorDescription,
    ) -> None:
        super().__init__(coordinator, device_id)
        self.entity_description = description
        self._attr_unique_id = f"{device_id}_{description.key}"

    @property
    def native_value(self) -> Any:
        device = self.device
        if device is None:
            return None
        return self.entity_description.value_fn(device)
