from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CURRENCY_EURO
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_MESSAGE,
    ATTR_MODE,
    ATTR_NAME,
    ATTR_PLATE,
    ATTR_SUCCESS,
    ATTR_TIME,
    ATTR_VERIFIED,
    DATA_LAST_ACTION,
    DOMAIN,
    SIGNAL_LAST_ACTION_UPDATED,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]

    async_add_entities(
        [
            TwoParkBalanceSensor(coordinator, entry),
            TwoParkMemberCountSensor(coordinator, entry),
            TwoParkLastUpdateSensor(coordinator, entry),
            TwoParkLastActionSensor(hass, coordinator, entry),
        ]
    )


class TwoParkBaseSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self.entry = entry

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.entry.entry_id)},
            "name": "2Park",
            "manufacturer": "Custom",
            "model": "2Park Local API",
        }


class TwoParkBalanceSensor(TwoParkBaseSensor):
    _attr_has_entity_name = True
    _attr_name = "Balance"
    _attr_native_unit_of_measurement = CURRENCY_EURO
    _attr_icon = "mdi:cash"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_balance"

    @property
    def native_value(self):
        return self.coordinator.data.balance.get("amount")

    @property
    def extra_state_attributes(self):
        return {
            "currency": self.coordinator.data.balance.get("currency"),
            "last_modified": self.coordinator.data.balance.get("last_modified"),
        }


class TwoParkMemberCountSensor(TwoParkBaseSensor):
    _attr_has_entity_name = True
    _attr_name = "Member count"
    _attr_icon = "mdi:account-multiple"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_member_count"

    @property
    def native_value(self):
        return len(self.coordinator.data.members)


class TwoParkLastUpdateSensor(TwoParkBaseSensor):
    _attr_has_entity_name = True
    _attr_name = "Last update"
    _attr_icon = "mdi:clock-refresh"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_last_update"

    @property
    def native_value(self):
        value = self.coordinator.data.last_update
        if not value:
            return None
        return datetime.fromisoformat(value)


class TwoParkLastActionSensor(TwoParkBaseSensor):
    _attr_has_entity_name = True
    _attr_name = "Last action"
    _attr_icon = "mdi:check-decagram"

    def __init__(self, hass: HomeAssistant, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self.hass = hass
        self._attr_unique_id = f"{entry.entry_id}_last_action"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SIGNAL_LAST_ACTION_UPDATED}_{self.entry.entry_id}",
                self.async_write_ha_state,
            )
        )

    @property
    def native_value(self):
        payload = self.hass.data[DOMAIN][self.entry.entry_id].get(DATA_LAST_ACTION, {})
        return payload.get(ATTR_MODE, "idle")

    @property
    def extra_state_attributes(self):
        payload = self.hass.data[DOMAIN][self.entry.entry_id].get(DATA_LAST_ACTION, {})
        return {
            ATTR_SUCCESS: payload.get(ATTR_SUCCESS),
            ATTR_VERIFIED: payload.get(ATTR_VERIFIED),
            ATTR_PLATE: payload.get(ATTR_PLATE),
            ATTR_NAME: payload.get(ATTR_NAME),
            ATTR_MESSAGE: payload.get(ATTR_MESSAGE),
            ATTR_TIME: payload.get(ATTR_TIME),
        }