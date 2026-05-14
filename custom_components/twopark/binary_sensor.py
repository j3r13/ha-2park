from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    async_add_entities(
        [TwoParkActiveSessionBinarySensor(coordinator, entry)]
    )


class TwoParkActiveSessionBinarySensor(
    CoordinatorEntity,
    BinarySensorEntity,
):
    _attr_has_entity_name = True
    _attr_name = "Active Parking Session"
    _attr_icon = "mdi:parking"
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)

        self._attr_unique_id = (
            f"{entry.entry_id}_active_parking_session"
        )

        self.entry = entry

    @property
    def is_on(self) -> bool:
        members = self.coordinator.data.members

        return any(
            bool(member.get("active"))
            for member in members
        )

    @property
    def extra_state_attributes(self):
        members = self.coordinator.data.members

        active_members = [
            member
            for member in members
            if bool(member.get("active"))
        ]

        return {
            "count": len(active_members),
            "active_plates": [
                member.get("plate")
                for member in active_members
                if member.get("plate")
            ],
            "active_sessions": active_members,
        }

    @property
    def device_info(self):
        return {
            "identifiers": {
                (DOMAIN, self.entry.entry_id)
            },
            "name": "2Park",
            "manufacturer": "2Park",
        }