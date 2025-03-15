"""Models an on/off device."""
from __future__ import annotations
from typing import Any

from .. import ApiSession
from ..info import HomeInfo

from .device import Device
from .const import DeviceType, DeviceTypeId


class OnOffDevice(Device):
    """Models an on/off device with a single on/off state and command."""

    def __init__(
        self,
        session: ApiSession,
        home: HomeInfo,
        data: dict,
        device_type: str | DeviceType,
        device_type_id: str | DeviceType
    ) -> None:
        super().__init__(session, home, data, device_type, device_type_id, do_update=False)
        self.is_on: bool = False
        self.update(data)

    def update(self, data: dict[str, Any]):
        """Update the radiator from cloud API data."""
        super().update(data)
        self.is_on = data["on_off"] == "1"

    async def set_onoff_state(self, turn_on: bool):
        """Set the onoff state, on (true) or off (false)"""
        if turn_on == self.is_on:
            return

        query_params = {}
        query_params["id_device"] = self.id_local
        query_params["on_off"] = "1" if turn_on else "0"

        await self._session.write_query(self.home.home_id, query_params)

        # This is debatable - for some scenarios it is reasonable to
        # update the value in the current object with the assumed
        # change, for others not
        self.is_on = turn_on

class Light(OnOffDevice):
    """Models a light."""

    def __init__(
        self,
        session: ApiSession,
        home: HomeInfo,
        data: dict
    ) -> None:
        super().__init__(session, home, data, DeviceType.LIGHT, DeviceTypeId.LIGHT)

class Outlet(OnOffDevice):
    """Models an outlet."""

    def __init__(
        self,
        session: ApiSession,
        home: HomeInfo,
        data: dict
    ) -> None:
        super().__init__(session, home, data, DeviceType.OUTLET, DeviceTypeId.OUTLET)
