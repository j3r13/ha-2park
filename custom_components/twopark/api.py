from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

import aiohttp

from .const import DEFAULT_BASE_URL, DEFAULT_LOCALE

_LOGGER = logging.getLogger(__name__)


class TwoParkApiError(Exception):
    """Base 2Park API error."""


class TwoParkAuthError(TwoParkApiError):
    """Authentication error."""


class TwoParkApiConnectionError(TwoParkApiError):
    """Connection error."""


def normalize_plate(plate: str) -> str:
    return plate.strip().upper().replace("-", "").replace(" ", "")


class TwoParkApiClient:
    """Async client for the undocumented 2Park web endpoints."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        email: str,
        password: str,
        product_id: str | None = None,
        location: str | None = None,
        locale: str = DEFAULT_LOCALE,
        base_url: str = DEFAULT_BASE_URL,
    ) -> None:
        self._session = session
        self.email = email
        self.password = password
        self.product_id = product_id or None
        self.location = location or None
        self.locale = locale or DEFAULT_LOCALE
        self.base_url = base_url.rstrip("/")
        self._logged_in = False

    def _url(self, endpoint: str) -> str:
        return f"{self.base_url}/gsmpark-app-www/json/{endpoint}"

    async def _post_form(
        self,
        endpoint: str,
        data: dict[str, Any],
        *,
        referer: str | None = None,
    ) -> dict[str, Any]:
        url = self._url(endpoint)
        headers = {
            "Accept": "*/*",
            "Origin": self.base_url,
            "Referer": referer or f"{self.base_url}/",
            "User-Agent": "Mozilla/5.0",
        }

        try:
            async with self._session.post(
                url,
                data=data,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                resp.raise_for_status()
                return await resp.json()
        except asyncio.TimeoutError as err:
            raise TwoParkApiConnectionError(f"Timeout naar {url}") from err
        except aiohttp.ClientResponseError as err:
            raise TwoParkApiConnectionError(f"2Park HTTP fout {err.status} voor {url}") from err
        except aiohttp.ClientError as err:
            raise TwoParkApiConnectionError(f"Verbindingsfout naar {url}: {err}") from err
        except ValueError as err:
            raise TwoParkApiError(f"Ongeldige JSON response van {url}") from err

    @staticmethod
    def _assert_ok(payload: dict[str, Any], expected_minor: str | None = None) -> None:
        status = payload.get("status", {})
        code = status.get("code", {})
        major = code.get("major")
        minor = code.get("minor")
        message = status.get("message", "")

        if major != "OK":
            raise TwoParkApiError(f"2Park fout: major={major!r}, minor={minor!r}, message={message!r}")

        if expected_minor is not None and minor != expected_minor:
            raise TwoParkApiError(
                f"Onverwachte 2Park status: verwacht minor={expected_minor!r}, kreeg {minor!r}"
            )

    async def async_login(self) -> dict[str, Any]:
        payload = await self._post_form(
            "check_credentials.json",
            {
                "email": self.email,
                "password": self.password,
                "locale": self.locale,
            },
            referer=f"{self.base_url}/login",
        )
        self._assert_ok(payload, expected_minor="AUTHENTICATED")
        self._logged_in = True
        _LOGGER.info("2Park login geslaagd")
        return payload

    async def async_ensure_logged_in(self) -> None:
        if not self._logged_in:
            await self.async_login()
            return

        if not self.product_id:
            return

        try:
            await self.async_get_product_details_raw(ensure_login=False)
        except Exception:
            _LOGGER.info("2Park sessie ongeldig of verlopen, opnieuw inloggen")
            self._logged_in = False
            await self.async_login()

    async def async_get_categories(self) -> dict[str, Any]:
        await self.async_ensure_logged_in()
        payload = await self._post_form(
            "get_categories.json",
            {"locale": self.locale},
        )
        self._assert_ok(payload, expected_minor="SUCCESS")
        return payload

    @staticmethod
    def _find_default_location(product: dict[str, Any]) -> str | None:
        for group in product.get("pdt_parameter_groups", []):
            if group.get("pgp_label") != "START":
                continue
            for param in group.get("pgp_parameters", []):
                if param.get("prr_label") == "LOCATION":
                    return param.get("prr_default_value")
        return None

    async def async_discover_defaults(self) -> dict[str, Any]:
        categories = await self.async_get_categories()
        found_products: list[dict[str, Any]] = []

        for category in categories.get("data", {}).get("categories", []):
            for product in category.get("cty_products", []):
                if product.get("pdt_is_blocked") == "true":
                    continue
                found_products.append({"category": category, "product": product})

        if not found_products:
            raise TwoParkApiError("Geen bruikbaar 2Park product gevonden")

        selected = found_products[0]
        product = selected["product"]
        category = selected["category"]

        discovered_product_id = product.get("pdt_id")
        discovered_location = self._find_default_location(product)

        if not discovered_product_id:
            raise TwoParkApiError("Geen product_id gevonden in 2Park response")

        if not self.product_id:
            self.product_id = discovered_product_id
        if not self.location:
            self.location = discovered_location

        return {
            "product_id": self.product_id,
            "location": self.location,
            "product_name": product.get("pdt_name"),
            "category_name": category.get("cty_name"),
            "product_count": len(found_products),
        }

    async def async_prepare(self) -> dict[str, Any]:
        await self.async_login()
        return await self.async_discover_defaults()

    async def async_get_product_details_raw(self, *, ensure_login: bool = True) -> dict[str, Any]:
        if ensure_login:
            await self.async_ensure_logged_in()

        if not self.product_id:
            await self.async_discover_defaults()

        payload = await self._post_form(
            "get_category_product_details.json",
            {
                "product_id": self.product_id,
                "locale": self.locale,
            },
        )
        self._assert_ok(payload, expected_minor="SUCCESS")
        return payload

    async def async_get_balance_raw(self) -> dict[str, Any]:
        await self.async_ensure_logged_in()
        if not self.product_id:
            await self.async_discover_defaults()

        payload = await self._post_form(
            "get_balance.json",
            {
                "product_id": self.product_id,
                "locale": self.locale,
            },
        )
        self._assert_ok(payload, expected_minor="SUCCESS")
        return payload

    @staticmethod
    def _extract_nickname(member: dict[str, Any]) -> str | None:
        for param in member.get("mbr_parameters", []):
            if param.get("prr_label") == "NICKNAME":
                return param.get("prr_value")
        return None

    @staticmethod
    def _extract_active_action(member: dict[str, Any]) -> dict[str, Any] | None:
        for action in member.get("mbr_actions", []):
            if action.get("atn_state") == "ACTIVE":
                return action
        return None

    @staticmethod
    def _extract_action_param(action: dict[str, Any] | None, label: str) -> str | None:
        if not action:
            return None
        for param in action.get("atn_parameters", []):
            if param.get("prr_label") == label:
                return param.get("prr_value")
        return None

    async def async_get_members(self) -> list[dict[str, Any]]:
        details = await self.async_get_product_details_raw()
        members = details.get("data", {}).get("pdt_members", [])

        result: list[dict[str, Any]] = []
        for member in members:
            plate = member.get("mbr_identifier", "")
            nickname = self._extract_nickname(member)
            active_action = self._extract_active_action(member)
            normalized_plate = normalize_plate(plate)

            result.append(
                {
                    "nickname": nickname,
                    "plate": normalized_plate,
                    "active": member.get("mbr_active") == "YES",
                    "action_id": active_action.get("atn_id") if active_action else None,
                    "time_start": self._extract_action_param(active_action, "TIMESTART"),
                    "time_end": self._extract_action_param(active_action, "TIMEEND"),
                    "location": self._extract_action_param(active_action, "LOCATION"),
                    "location_code": self._extract_action_param(active_action, "LOC_CODE"),
                }
            )

        return result

    async def async_get_balance(self) -> dict[str, Any]:
        payload = await self.async_get_balance_raw()
        params = payload.get("data", {}).get("balance", {}).get("ble_parameters", [])

        def get_param(label: str) -> str | None:
            for param in params:
                if param.get("prr_label") == label:
                    return param.get("prr_value")
            return None

        amount_raw = get_param("AMOUNT")
        try:
            amount = float(amount_raw) if amount_raw is not None else None
        except ValueError:
            amount = None

        return {
            "amount": amount,
            "currency": get_param("CURRENCY_DESC") or "€",
            "last_modified": get_param("LAST_MODIFIED"),
        }

    async def async_find_member_by_plate(self, plate: str) -> dict[str, Any] | None:
        plate_norm = normalize_plate(plate)
        details = await self.async_get_product_details_raw()
        for member in details.get("data", {}).get("pdt_members", []):
            if normalize_plate(member.get("mbr_identifier", "")) == plate_norm:
                return member
        return None

    async def async_find_member_by_name(self, name: str) -> dict[str, Any] | None:
        name_norm = name.strip().lower()
        details = await self.async_get_product_details_raw()
        for member in details.get("data", {}).get("pdt_members", []):
            nickname = self._extract_nickname(member)
            if nickname and nickname.strip().lower() == name_norm:
                return member
        return None

    async def async_resolve_plate(self, plate: str | None = None, name: str | None = None) -> str:
        if plate:
            return normalize_plate(plate)
        if name:
            member = await self.async_find_member_by_name(name)
            if not member:
                raise TwoParkApiError(f"Geen favoriet gevonden met naam {name!r}")
            found_plate = member.get("mbr_identifier")
            if not found_plate:
                raise TwoParkApiError(f"Favoriet {name!r} heeft geen kenteken")
            return normalize_plate(found_plate)
        raise TwoParkApiError("Geen kenteken of naam opgegeven")

    async def async_get_active_action_for_plate(self, plate: str) -> dict[str, Any] | None:
        member = await self.async_find_member_by_plate(plate)
        if not member:
            return None
        return self._extract_active_action(member)

    async def async_start(
        self,
        plate: str,
        *,
        location: str | None = None,
        time_start: str | None = None,
        time_end: str | None = None,
    ) -> dict[str, Any]:
        await self.async_ensure_logged_in()
        if not self.product_id or not self.location:
            await self.async_discover_defaults()

        plate = normalize_plate(plate)
        location_value = location or self.location
        now = datetime.now()
        time_start = time_start or now.strftime("%d-%m-%Y %H:%M:%S")
        time_end = time_end or now.strftime("%d-%m-%Y") + " 23:59:59"

        action_payload = {
            "action": {
                "atn_parameters": [
                    {"prr_label": "MBR_IDENT", "prr_value": plate},
                    {"prr_label": "TIMESTART", "prr_value": time_start},
                    {"prr_label": "TIMEEND", "prr_value": time_end},
                    {"prr_label": "LOCATION", "prr_value": location_value},
                ]
            }
        }

        payload = await self._post_form(
            "start_action.json",
            {
                "data": json.dumps(action_payload, separators=(",", ":")),
                "locale": self.locale,
                "product_id": self.product_id,
            },
        )
        self._assert_ok(payload)
        verify = await self.async_verify_state(plate, expected_active=True)
        result = {"success": True, "plate": plate, "mode": "started", "raw": payload}
        result.update(verify)
        if not verify["verified"]:
            result["success"] = False
            result["error"] = "Start niet bevestigd"
        return result

    async def async_stop_action(self, action_id: str) -> dict[str, Any]:
        await self.async_ensure_logged_in()
        if not self.product_id:
            await self.async_discover_defaults()

        payload = await self._post_form(
            "stop_action.json",
            {
                "action_id": str(action_id),
                "locale": self.locale,
                "product_id": self.product_id,
            },
        )
        self._assert_ok(payload, expected_minor="SUCCESS")
        return {"success": True, "action_id": str(action_id), "mode": "stopped", "raw": payload}

    async def async_stop(self, plate: str) -> dict[str, Any]:
        plate = normalize_plate(plate)
        active_action = await self.async_get_active_action_for_plate(plate)
        if not active_action:
            raise TwoParkApiError(f"Geen actieve parkeeractie gevonden voor {plate}")

        action_id = active_action.get("atn_id")
        if not action_id:
            raise TwoParkApiError(f"Actieve parkeeractie gevonden voor {plate}, maar zonder action_id")

        result = await self.async_stop_action(action_id)
        verify = await self.async_verify_state(plate, expected_active=False)
        result.update(verify)
        if not verify["verified"]:
            result["success"] = False
            result["error"] = "Stop niet bevestigd"
        result["plate"] = plate
        return result

    async def async_toggle(self, *, plate: str | None = None, name: str | None = None) -> dict[str, Any]:
        resolved_plate = await self.async_resolve_plate(plate=plate, name=name)
        active_action = await self.async_get_active_action_for_plate(resolved_plate)
        if active_action:
            result = await self.async_stop(resolved_plate)
        else:
            result = await self.async_start(resolved_plate)
        if name:
            result["name"] = name
        return result

    async def async_verify_state(
        self,
        plate: str,
        expected_active: bool,
        retries: int = 3,
        delay: float = 1.0,
    ) -> dict[str, Any]:
        plate = normalize_plate(plate)
        await self.async_ensure_logged_in()

        for attempt in range(1, retries + 1):
            _LOGGER.info("2Park verificatie poging %s/%s voor %s", attempt, retries, plate)
            details = await self.async_get_product_details_raw()
            members = details.get("data", {}).get("pdt_members", [])

            matching_member = None
            for member in members:
                if normalize_plate(member.get("mbr_identifier", "")) == plate:
                    matching_member = member
                    break

            if expected_active:
                if matching_member and matching_member.get("mbr_active") == "YES":
                    for action in matching_member.get("mbr_actions", []):
                        if action.get("atn_state") == "ACTIVE":
                            return {"verified": True, "action_id": action.get("atn_id")}
            else:
                if matching_member is None:
                    return {"verified": True, "action_id": None}
                if matching_member.get("mbr_active") != "YES":
                    return {"verified": True, "action_id": None}

            await asyncio.sleep(delay)

        return {"verified": False, "action_id": None}
