"""Define general constants"""
from enum import IntEnum
from ..util import StrEnum


class DeviceType(StrEnum):
    """Recognized device types"""

    RADIATOR = "Radiator"
    LIGHT = "Light"
    OUTLET = "Outlet"
    UNKNOWN = "Unknown"

class DeviceTypeId(IntEnum):
    """Recognized device type ids"""

    RADIATOR = 0
    LIGHT = 1
    OUTLET = 12
