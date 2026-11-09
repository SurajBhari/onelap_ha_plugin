"""Binary sensor platform for Onelap — ignition / online state."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import OnelapConfigEntry
from .coordinator import OnelapDataUpdateCoordinator
from .entity import OnelapEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OnelapConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Onelap binary sensors."""
    coordinator = entry.runtime_data
    known: set[int] = set()

    @callback
    def _add_new_devices() -> None:
        new = [
            OnelapIgnitionSensor(coordinator, device_id)
            for device_id in coordinator.data
            if device_id not in known
        ]
        if new:
            known.update(e._device_id for e in new)
            async_add_entities(new)

    _add_new_devices()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_devices))


class OnelapIgnitionSensor(OnelapEntity, BinarySensorEntity):
    """Reports whether the vehicle ignition is on."""

    _attr_translation_key = "ignition"
    _attr_device_class = BinarySensorDeviceClass.POWER
    _attr_icon = "mdi:key-variant"

    def __init__(
        self, coordinator: OnelapDataUpdateCoordinator, device_id: int
    ) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_ignition"

    @property
    def is_on(self) -> bool | None:
        device = self.device
        if device is None or device.position is None:
            return None
        pos_attrs = device.position.get("attributes") or {}
        if "ignition" in pos_attrs:
            return bool(pos_attrs["ignition"])
        if device.position.get("ignitionOn") is not None:
            return bool(device.position.get("ignitionOn"))
        return None
