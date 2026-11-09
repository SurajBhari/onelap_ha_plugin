"""Shared entity base for Onelap entities."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import OnelapDataUpdateCoordinator, OnelapDevice


class OnelapEntity(CoordinatorEntity[OnelapDataUpdateCoordinator]):
    """Base class wiring an entity to one Onelap device."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: OnelapDataUpdateCoordinator, device_id: int
    ) -> None:
        super().__init__(coordinator)
        self._device_id = device_id

    @property
    def device(self) -> OnelapDevice | None:
        return self.coordinator.data.get(self._device_id)

    @property
    def available(self) -> bool:
        return super().available and self.device is not None

    @property
    def device_info(self) -> DeviceInfo:
        device = self.device
        name = device.name if device else f"Onelap {self._device_id}"
        model = None
        sw_version = None
        if device:
            model = device.attributes.get("hardwareCode")
            if device.vehicle_number:
                name = device.vehicle_number
        return DeviceInfo(
            identifiers={(DOMAIN, str(self._device_id))},
            name=name,
            manufacturer=MANUFACTURER,
            model=model,
            sw_version=sw_version,
            configuration_url="https://r.onelap.in/",
        )
