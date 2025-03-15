"""Define general constants"""
from enum import IntEnum
from ..util import StrEnum


class DeviceType(StrEnum):
    """Recognized device types"""

    RADIATOR = "Radiator"
    LIGHT = "Light"
    OUTLET = "Outlet"
    UNKNOWN = "Unknown"

class DeviceTypeId(StrEnum):
    """Recognized device type ids"""

    RADIATOR = "C"
    LIGHT = "E"
    OUTLET = "O"
    UNDEFINED = "U"
