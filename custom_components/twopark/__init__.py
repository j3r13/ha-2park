from __future__ import annotations

from datetime import datetime

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .api import TwoParkApiClient
from .const import (
    ATTR_MESSAGE,
    ATTR_MODE,
    ATTR_NAME,
    ATTR_PLATE,
    ATTR_SUCCESS,
    ATTR_TIME,
    ATTR_VERIFIED,
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_PRODUCT_ID,
    CONF_LOCATION,
    CONF_LOCALE,
    CONF_SCAN_INTERVAL,
    DATA_LAST_ACTION,
    DEFAULT_LOCALE,
    DOMAIN,
    SERVICE_START_PLATE,
    SERVICE_STOP_PLATE,
    SERVICE_TOGGLE_PLATE,
    SIGNAL_LAST_ACTION_UPDATED,
)
from .coordinator import TwoParkCoordinator

PLATFORMS: list[Platform] = [
    Platform.SWITCH,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
]


def _get_first_entry_id(hass: HomeAssistant) -> str:
    domain_data = hass.data.get(DOMAIN, {})
    if not domain_data:
        raise ValueError("Geen actieve 2Park configuratie gevonden")
    return next(iter(domain_data))


def _get_first_entry_data(hass: HomeAssistant) -> dict:
    entry_id = _get_first_entry_id(hass)
    return hass.data[DOMAIN][entry_id]


def _set_last_action(hass: HomeAssistant, entry_id: str, payload: dict) -> None:
    hass.data[DOMAIN][entry_id][DATA_LAST_ACTION] = payload
    async_dispatcher_send(hass, f"{SIGNAL_LAST_ACTION_UPDATED}_{entry_id}")


def _last_action_payload(result: dict, mode: str, plate: str, name: str | None = None) -> dict:
    verified = result.get("verified")
    if mode == "started":
        message = "Parkeeractie gestart" if verified else result.get("error", "Start niet bevestigd")
    elif mode == "stopped":
        message = "Parkeeractie gestopt" if verified else result.get("error", "Stop niet bevestigd")
    else:
        message = result.get("error", "Actie niet bevestigd")

    return {
        ATTR_MODE: mode,
        ATTR_SUCCESS: bool(result.get("success")),
        ATTR_VERIFIED: verified,
        ATTR_PLATE: result.get("plate", plate),
        ATTR_NAME: result.get("name", name),
        ATTR_MESSAGE: message,
        ATTR_TIME: datetime.now().isoformat(),
    }


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = async_get_clientsession(hass)
    api = TwoParkApiClient(
        session=session,
        email=entry.data[CONF_EMAIL],
        password=entry.data[CONF_PASSWORD],
        product_id=entry.data.get(CONF_PRODUCT_ID),
        location=entry.data.get(CONF_LOCATION),
        locale=entry.data.get(CONF_LOCALE, DEFAULT_LOCALE),
    )
    coordinator = TwoParkCoordinator(
        hass,
        api,
        entry.options.get(CONF_SCAN_INTERVAL, entry.data.get(CONF_SCAN_INTERVAL, 30)),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
        DATA_LAST_ACTION: {
            ATTR_MODE: "idle",
            ATTR_SUCCESS: True,
            ATTR_VERIFIED: None,
            ATTR_PLATE: None,
            ATTR_NAME: None,
            ATTR_MESSAGE: "Nog geen actie uitgevoerd",
            ATTR_TIME: datetime.now().isoformat(),
        },
    }

    if not hass.services.has_service(DOMAIN, SERVICE_START_PLATE):

        async def handle_start_plate(call: ServiceCall) -> None:
            plate = call.data[ATTR_PLATE]
            entry_id = _get_first_entry_id(hass)
            entry_data = _get_first_entry_data(hass)
            result = await entry_data["api"].async_start(plate)
            _set_last_action(hass, entry_id, _last_action_payload(result, "started", plate))
            await entry_data["coordinator"].async_request_refresh()

        async def handle_stop_plate(call: ServiceCall) -> None:
            plate = call.data[ATTR_PLATE]
            entry_id = _get_first_entry_id(hass)
            entry_data = _get_first_entry_data(hass)
            result = await entry_data["api"].async_stop(plate)
            _set_last_action(hass, entry_id, _last_action_payload(result, "stopped", plate))
            await entry_data["coordinator"].async_request_refresh()

        async def handle_toggle_plate(call: ServiceCall) -> None:
            plate = call.data[ATTR_PLATE]
            entry_id = _get_first_entry_id(hass)
            entry_data = _get_first_entry_data(hass)
            result = await entry_data["api"].async_toggle(plate=plate)
            mode = result.get("mode", "unknown")
            _set_last_action(hass, entry_id, _last_action_payload(result, mode, plate))
            await entry_data["coordinator"].async_request_refresh()

        hass.services.async_register(
            DOMAIN,
            SERVICE_START_PLATE,
            handle_start_plate,
            schema=vol.Schema({vol.Required(ATTR_PLATE): cv.string}),
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_STOP_PLATE,
            handle_stop_plate,
            schema=vol.Schema({vol.Required(ATTR_PLATE): cv.string}),
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_TOGGLE_PLATE,
            handle_toggle_plate,
            schema=vol.Schema({vol.Required(ATTR_PLATE): cv.string}),
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    if not hass.data.get(DOMAIN):
        for service in (SERVICE_START_PLATE, SERVICE_STOP_PLATE, SERVICE_TOGGLE_PLATE):
            if hass.services.has_service(DOMAIN, service):
                hass.services.async_remove(DOMAIN, service)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
