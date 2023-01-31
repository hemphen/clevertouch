"""Factory for creating devices of specific types."""
from __future__ import annotations
from typing import Any

from ..api import ApiSession
from ..info import HomeInfo
from .device import Device
from .const import DeviceType
from .radiator import Radiator


def create_device(session: ApiSession, home: HomeInfo, data: dict[str, Any]) -> Device:
    """Create a device of of specific types based on the provided data."""
    nv_mode = data["nv_mode"]
    if nv_mode == "0":
        return Radiator(session, home, data)
    elif nv_mode == "1":
        return Device(session, home, data, DeviceType.LIGHT)
    elif nv_mode == "12":
        return Device(session, home, data, DeviceType.OUTLET)
    else:
        return Device(session, home, data, DeviceType.UNKNOWN)
