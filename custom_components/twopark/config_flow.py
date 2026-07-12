from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import TwoParkApiClient, TwoParkApiConnectionError, TwoParkApiError
from .const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_PRODUCT_ID,
    CONF_PRODUCT_NAME,
    CONF_LOCATION,
    CONF_LOCALE,
    CONF_SCAN_INTERVAL,
    DEFAULT_LOCALE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 2

    def __init__(self) -> None:
        super().__init__()
        self._input_data: dict | None = None
        self._products: list[dict] | None = None

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            email = user_input[CONF_EMAIL].strip()
            password = user_input[CONF_PASSWORD]
            locale = user_input.get(CONF_LOCALE, DEFAULT_LOCALE)
            scan_interval = user_input[CONF_SCAN_INTERVAL]

            session = async_get_clientsession(self.hass)
            client = TwoParkApiClient(
                session=session,
                email=email,
                password=password,
                locale=locale,
            )

            try:
                await client.async_login()
                products = await client.async_discover_products()
            except TwoParkApiConnectionError:
                errors["base"] = "cannot_connect"
            except TwoParkApiError:
                errors["base"] = "invalid_auth"
            except Exception:
                errors["base"] = "unknown"
            else:
                self._input_data = {
                    CONF_EMAIL: email,
                    CONF_PASSWORD: password,
                    CONF_LOCALE: locale,
                    CONF_SCAN_INTERVAL: scan_interval,
                }
                self._products = products

                if len(products) == 1:
                    return await self._async_create_entry(products[0])

                return await self.async_step_product()

        schema = vol.Schema(
            {
                vol.Required(CONF_EMAIL): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Optional(CONF_LOCALE, default=DEFAULT_LOCALE): str,
                vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_product(self, user_input=None):
        if user_input is not None:
            selected_product_id = user_input[CONF_PRODUCT_ID]
            selected = next(
                (p for p in self._products if p["product_id"] == selected_product_id),
                None,
            )
            if selected is None:
                return self.async_show_form(
                    step_id="product",
                    data_schema=self._product_schema(),
                    errors={"base": "unknown"},
                )
            return await self._async_create_entry(selected)

        return self.async_show_form(
            step_id="product",
            data_schema=self._product_schema(),
        )

    def _product_schema(self) -> vol.Schema:
        choices = {}
        for p in self._products:
            name = p.get("product_name") or p["product_id"]
            category = p.get("category_name")
            label = f"{name} ({category})" if category else name
            choices[p["product_id"]] = label
        return vol.Schema({vol.Required(CONF_PRODUCT_ID): vol.In(choices)})

    async def _async_create_entry(self, product: dict):
        email = self._input_data[CONF_EMAIL]
        product_id = product["product_id"]
        product_name = product.get("product_name") or product_id

        unique_id = f"{email.lower()}_{product_id}"
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        data = {
            **self._input_data,
            CONF_PRODUCT_ID: product_id,
            CONF_PRODUCT_NAME: product_name,
            CONF_LOCATION: product.get("location") or "",
        }

        return self.async_create_entry(
            title=f"2Park ({email} – {product_name})",
            data=data,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlowHandler()


class OptionsFlowHandler(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL,
            self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )

        schema = vol.Schema({vol.Required(CONF_SCAN_INTERVAL, default=current_interval): int})
        return self.async_show_form(step_id="init", data_schema=schema)
