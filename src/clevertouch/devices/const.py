"""Define general constants"""
from ..util import StrEnum


class DeviceType(StrEnum):
    """Recognized device types"""

    RADIATOR = "Radiator"
    LIGHT = "Light"
    OUTLET = "Outlet"
    UNKNOWN = "Unknown"
