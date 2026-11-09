"""Device tracker platform for Onelap — puts the vehicle on the HA map."""

from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import OnelapConfigEntry
from .const import ATTR_TRACKING_ID, KNOTS_TO_KMPH
from .coordinator import OnelapDataUpdateCoordinator
from .entity import OnelapEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OnelapConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Onelap device trackers, following devices as they appear."""
    coordinator = entry.runtime_data
    known: set[int] = set()

    @callback
    def _add_new_devices() -> None:
        new = [
            OnelapDeviceTracker(coordinator, device_id)
            for device_id in coordinator.data
            if device_id not in known
        ]
        if new:
            known.update(e._device_id for e in new)
            async_add_entities(new)

    _add_new_devices()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_devices))


class OnelapDeviceTracker(OnelapEntity, TrackerEntity):
    """A single Onelap vehicle shown on the Home Assistant map."""

    _attr_name = None  # Use the device name for the tracker entity.
    _attr_icon = "mdi:car"

    def __init__(
        self, coordinator: OnelapDataUpdateCoordinator, device_id: int
    ) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_tracker"

    @property
    def source_type(self) -> SourceType:
        return SourceType.GPS

    @property
    def latitude(self) -> float | None:
        device = self.device
        return device.latitude if device and device.has_fix else None

    @property
    def longitude(self) -> float | None:
        device = self.device
        return device.longitude if device and device.has_fix else None

    @property
    def location_accuracy(self) -> int:
        # Onelap does not report an accuracy radius; 0 = exact per HA convention.
        return 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        device = self.device
        attrs: dict[str, Any] = {ATTR_TRACKING_ID: self.coordinator.client.tracking_id}
        if device is None:
            return attrs

        if device.vehicle_number:
            attrs["vehicle_number"] = device.vehicle_number
        if device.status:
            attrs["status"] = device.status
        if device.last_update:
            attrs["last_update"] = device.last_update

        pos = device.position or {}
        speed_knots = pos.get("speed")
        if isinstance(speed_knots, (int, float)):
            attrs["speed_kmph"] = round(speed_knots * KNOTS_TO_KMPH, 1)
        course = pos.get("course")
        if isinstance(course, (int, float)):
            attrs["course"] = course
        if pos.get("fixTime"):
            attrs["gps_time"] = pos.get("fixTime")
        pos_attrs = pos.get("attributes") or {}
        if "ignition" in pos_attrs:
            attrs["ignition"] = bool(pos_attrs.get("ignition"))
        if "sat" in pos_attrs:
            attrs["satellites"] = pos_attrs.get("sat")
        if "totalDistance" in pos_attrs:
            # metres -> km
            attrs["total_distance_km"] = round(
                float(pos_attrs["totalDistance"]) / 1000, 2
            )
        return attrs
