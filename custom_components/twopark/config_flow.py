from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.exceptions import HomeAssistantError

from .api import TwoParkApiClient, TwoParkApiConnectionError, TwoParkApiError
from .const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_PRODUCT_ID,
    CONF_LOCATION,
    CONF_LOCALE,
    CONF_SCAN_INTERVAL,
    DEFAULT_LOCALE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)


async def validate_input(hass, data):
    session = async_get_clientsession(hass)
    client = TwoParkApiClient(
        session=session,
        email=data[CONF_EMAIL],
        password=data[CONF_PASSWORD],
        product_id=(data.get(CONF_PRODUCT_ID) or None),
        location=(data.get(CONF_LOCATION) or None),
        locale=data.get(CONF_LOCALE, DEFAULT_LOCALE),
    )

    try:
        discovered = await client.async_prepare()
    except TwoParkApiConnectionError as err:
        raise CannotConnect from err
    except TwoParkApiError as err:
        raise InvalidAuth from err

    result = dict(data)
    result[CONF_PRODUCT_ID] = discovered.get("product_id")
    result[CONF_LOCATION] = discovered.get("location")
    result[CONF_LOCALE] = data.get(CONF_LOCALE, DEFAULT_LOCALE)

    return {
        "title": f"2Park ({data[CONF_EMAIL]})",
        "data": result,
    }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_EMAIL].strip().lower())
            self._abort_if_unique_id_configured()

            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=info["data"])

        schema = vol.Schema(
            {
                vol.Required(CONF_EMAIL): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Optional(CONF_PRODUCT_ID, default=""): str,
                vol.Optional(CONF_LOCATION, default=""): str,
                vol.Optional(CONF_LOCALE, default=DEFAULT_LOCALE): str,
                vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL,
            self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )

        schema = vol.Schema({vol.Required(CONF_SCAN_INTERVAL, default=current_interval): int})
        return self.async_show_form(step_id="init", data_schema=schema)


class CannotConnect(HomeAssistantError):
    """Cannot connect to 2Park."""


class InvalidAuth(HomeAssistantError):
    """Invalid 2Park auth or product discovery failed."""
