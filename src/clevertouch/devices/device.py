"""Models a device."""
from __future__ import annotations
from typing import Any

from ..api import ApiSession
from ..info import HomeInfo, ZoneInfo


class Device:
    """Models a generic device."""

    def __init__(
        self,
        session: ApiSession,
        home: HomeInfo,
        data: dict[str, Any],
        device_type: str,
    ) -> None:
        self.device_type: str = device_type
        self._session: ApiSession = session
        self.home: HomeInfo = home
        self.device_id: str = Device.get_id(data)
        self.update(data)

    def update(self, data: dict[str, Any]):
        """Update the device information from cloud API data"""
        assert self.device_id == Device.get_id(data)

        self.id_local: str = data["id_device"]
        self.label: str = data["label_interface"]
        self.zone: ZoneInfo = self.home.zones[data["num_zone"]]

    @classmethod
    def get_id(cls, data: dict[str, Any]) -> str:
        """Utility function to get the device id from cloud API data"""
        return data["id"]
