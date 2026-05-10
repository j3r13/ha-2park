from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import TwoParkApiClient, TwoParkApiError, normalize_plate
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class TwoParkData:
    members: list[dict]
    balance: dict
    member_map: dict[str, dict]
    last_update: str


def member_key(member: dict) -> str:
    plate = normalize_plate(member.get("plate", ""))
    return plate.lower()


class TwoParkCoordinator(DataUpdateCoordinator[TwoParkData]):
    def __init__(
        self,
        hass: HomeAssistant,
        api: TwoParkApiClient,
        scan_interval: int = DEFAULT_SCAN_INTERVAL,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.api = api

    async def _async_update_data(self) -> TwoParkData:
        try:
            members = await self.api.async_get_members()
            balance = await self.api.async_get_balance()
        except TwoParkApiError as err:
            raise UpdateFailed(str(err)) from err
        except Exception as err:
            raise UpdateFailed(str(err)) from err

        member_map = {
            member_key(member): member
            for member in members
            if normalize_plate(member.get("plate", "")) not in ("", "UNKNOWN", "UNAVAILABLE", "NONE", "NULL")
        }

        return TwoParkData(
            members=members,
            balance=balance,
            member_map=member_map,
            last_update=datetime.now().isoformat(),
        )
