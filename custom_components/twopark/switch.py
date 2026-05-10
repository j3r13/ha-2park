from __future__ import annotations

from datetime import datetime

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

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
from .coordinator import member_key
from .api import normalize_plate


def _set_last_action(hass: HomeAssistant, entry_id: str, payload: dict) -> None:
    hass.data[DOMAIN][entry_id][DATA_LAST_ACTION] = payload
    async_dispatcher_send(hass, f"{SIGNAL_LAST_ACTION_UPDATED}_{entry_id}")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    api = data["api"]

    known_entities: dict[str, TwoParkMemberSwitch] = {}

    async def sync_entities() -> None:
        current_members: dict[str, dict] = {}

        for member in coordinator.data.members:
            plate = normalize_plate(member.get("plate", ""))
            if plate in ("", "UNKNOWN", "UNAVAILABLE", "NONE", "NULL"):
                continue

            member_copy = dict(member)
            member_copy["plate"] = plate
            key = member_key(member_copy)
            current_members[key] = member_copy

        new_entities: list[TwoParkMemberSwitch] = []
        for key, member in current_members.items():
            if key in known_entities:
                known_entities[key].update_member_snapshot(member)
                continue

            entity = TwoParkMemberSwitch(hass, coordinator, api, entry, key, member)
            known_entities[key] = entity
            new_entities.append(entity)

        if new_entities:
            async_add_entities(new_entities)

        stale_keys = [key for key in known_entities if key not in current_members]
        entity_registry = er.async_get(hass)

        for key in stale_keys:
            entity = known_entities.pop(key)
            await entity.async_remove()

            if entity.entity_id:
                registry_entry = entity_registry.async_get(entity.entity_id)
                if registry_entry:
                    entity_registry.async_remove(entity.entity_id)

    await sync_entities()

    @callback
    def _schedule_sync() -> None:
        hass.async_create_task(sync_entities())

    entry.async_on_unload(coordinator.async_add_listener(_schedule_sync))


class TwoParkMemberSwitch(CoordinatorEntity, SwitchEntity):
    _attr_has_entity_name = False

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator,
        api,
        entry: ConfigEntry,
        key: str,
        member: dict,
    ) -> None:
        super().__init__(coordinator)
        self.hass = hass
        self.api = api
        self.entry = entry
        self.member_id = key

        self._plate = normalize_plate(member.get("plate", ""))
        self._nickname = member.get("nickname")
        self._is_persistent = bool(self._nickname)
        self._attr_name = self._nickname or self._plate

        self._attr_unique_id = f"{entry.entry_id}_member_{self._plate.lower()}"
        self.entity_id = generate_entity_id(
            "switch.{}",
            f"2park_{slugify(self._plate)}",
            hass=hass,
        )

    def update_member_snapshot(self, member: dict) -> None:
        self._plate = normalize_plate(member.get("plate", "")) or self._plate
        self._nickname = member.get("nickname")
        self._is_persistent = bool(self._nickname)
        self._attr_name = self._nickname or self._plate
        self.async_write_ha_state()

    @property
    def _member(self) -> dict:
        return self.coordinator.data.member_map.get(self.member_id, {})

    @property
    def available(self) -> bool:
        return self.member_id in self.coordinator.data.member_map

    @property
    def is_on(self) -> bool:
        member = self._member
        return bool(member.get("active", False))

    @property
    def icon(self) -> str:
        return "mdi:car-connected"

    @property
    def extra_state_attributes(self):
        member = self._member
        return {
            "plate": member.get("plate", self._plate),
            "nickname": member.get("nickname", self._nickname),
            "action_id": member.get("action_id"),
            "time_start": member.get("time_start"),
            "time_end": member.get("time_end"),
            "location": member.get("location"),
            "location_code": member.get("location_code"),
            "persistent": self._is_persistent,
        }

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.entry.entry_id)},
            "name": "2Park",
            "manufacturer": "Custom",
            "model": "2Park Direct API",
        }

    async def async_turn_on(self, **kwargs) -> None:
        member = self._member
        plate = member.get("plate", self._plate)
        name = member.get("nickname", self._nickname)

        if not plate:
            return

        result = None
        if not self.is_on:
            result = await self.api.async_start(plate)

        await self.coordinator.async_request_refresh()

        if result is not None:
            payload = {
                ATTR_MODE: "started",
                ATTR_SUCCESS: bool(result.get("success")),
                ATTR_VERIFIED: result.get("verified"),
                ATTR_PLATE: result.get("plate", plate),
                ATTR_NAME: name,
                ATTR_MESSAGE: (
                    "Parkeeractie gestart"
                    if result.get("verified")
                    else result.get("error", "Start niet bevestigd")
                ),
                ATTR_TIME: datetime.now().isoformat(),
            }
            _set_last_action(self.hass, self.entry.entry_id, payload)

    async def async_turn_off(self, **kwargs) -> None:
        member = self._member
        plate = member.get("plate", self._plate)
        name = member.get("nickname", self._nickname)

        if not plate:
            return

        result = None
        if self.is_on:
            result = await self.api.async_stop(plate)

        await self.coordinator.async_request_refresh()

        if result is not None:
            payload = {
                ATTR_MODE: "stopped",
                ATTR_SUCCESS: bool(result.get("success")),
                ATTR_VERIFIED: result.get("verified"),
                ATTR_PLATE: result.get("plate", plate),
                ATTR_NAME: name,
                ATTR_MESSAGE: (
                    "Parkeeractie gestopt"
                    if result.get("verified")
                    else result.get("error", "Stop niet bevestigd")
                ),
                ATTR_TIME: datetime.now().isoformat(),
            }
            _set_last_action(self.hass, self.entry.entry_id, payload)
