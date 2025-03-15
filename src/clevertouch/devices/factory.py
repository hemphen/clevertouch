"""Factory for creating devices of specific types."""
from __future__ import annotations
from typing import Any

from ..api import ApiSession
from ..info import HomeInfo
from .device import Device
from .const import DeviceType, DeviceTypeId
from .onoff import Light, Outlet
from .radiator import Radiator


def create_device(session: ApiSession, home: HomeInfo, data: dict[str, Any]) -> Device:
    """Create a device of of specific types based on the provided data."""
    device_type_id = str(data.get("id_device", DeviceTypeId.UNDEFINED)[0])
    if device_type_id == DeviceTypeId.RADIATOR:
        return Radiator(session, home, data)
    elif device_type_id == DeviceTypeId.LIGHT:
        return Light(session, home, data)
    elif device_type_id == DeviceTypeId.OUTLET:
        return Outlet(session, home, data)
    else:
        return Device(session, home, data, DeviceType.UNKNOWN, device_type_id)
