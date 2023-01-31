"""Models a radiator."""
from __future__ import annotations
from typing import Optional, Any, NamedTuple

from .. import ApiSession, ApiError
from ..info import HomeInfo
from ..util import StrEnum

from .device import Device
from .const import DeviceType


class _ModeInfo(NamedTuple):
    heat_mode: HeatMode
    temp_mode: TempType


class HeatMode(StrEnum):
    """Enum of available heating modes for a radiator."""

    OFF = "Off"
    FROST = "Frost"
    COMFORT = "Comfort"
    PROGRAM = "Program"
    ECO = "Eco"
    BOOST = "Boost"


class TempType(StrEnum):
    """Enum of avaialable temperatures modes for a radiator."""

    NONE = "none"
    FROST = "frost"
    ECO = "eco"
    COMFORT = "comfort"
    BOOST = "boost"
    CURRENT = "current"
    TARGET = "target"
    MANUAL = "manual"


class Radiator(Device):
    """Models a radiator."""

    _DEVICE_TO_MODE_TYPE: dict[str, _ModeInfo] = {
        "0": _ModeInfo(HeatMode.COMFORT, TempType.COMFORT),
        "1": _ModeInfo(HeatMode.OFF, TempType.NONE),
        "2": _ModeInfo(HeatMode.COMFORT, TempType.COMFORT),
        "3": _ModeInfo(HeatMode.ECO, TempType.ECO),
        "4": _ModeInfo(HeatMode.BOOST, TempType.BOOST),
        # "5": ModeInfo("fan", None),
        # "6": ModeInfo("fan-disabled", None),
        "8": _ModeInfo(HeatMode.PROGRAM, TempType.COMFORT),
        "11": _ModeInfo(HeatMode.PROGRAM, TempType.ECO),
        # "13": ModeInfo("program", None),
        # "15": ModeInfo("manual", "manual"),
        # "16": ModeInfo("program", "boost"),
    }

    _HEAT_MODE_TO_DEVICE: dict[str, str] = {
        HeatMode.ECO: "3",
        HeatMode.FROST: "2",
        HeatMode.COMFORT: "0",
        HeatMode.PROGRAM: "11",
        HeatMode.OFF: "1",
    }

    _TEMP_TYPE_TO_DEVICE: dict[str, str] = {
        TempType.ECO: "consigne_eco",
        TempType.FROST: "consigne_hg",
        TempType.COMFORT: "consigne_confort",
        TempType.CURRENT: "temperature_air",
        TempType.MANUAL: "consigne_manuel",
        TempType.BOOST: "consigne_boost",
    }

    _AVAILABLE_TEMP_TYPES: list[str] = [
        TempType.ECO,
        TempType.FROST,
        TempType.COMFORT,
        TempType.CURRENT,
        TempType.BOOST,
    ]

    _READONLY_TEMP_TYPES: list[str] = [
        TempType.CURRENT,
        TempType.TARGET,
        TempType.BOOST,
    ]

    _AVAILABLE_HEAT_MODES: list[str] = [
        HeatMode.COMFORT,
        HeatMode.ECO,
        HeatMode.FROST,
        HeatMode.PROGRAM,
        HeatMode.OFF,
    ]

    def __init__(self, session: ApiSession, home: HomeInfo, data: dict) -> None:
        super().__init__(session, home, data, DeviceType.RADIATOR)
        self.modes: list[str] = self._AVAILABLE_HEAT_MODES

    def update(self, data: dict[str, Any]):
        """Update the radiator from cloud API data."""
        super().update(data)
        self.mode_num: str = data["gv_mode"]
        self._program_type: _ModeInfo = self._DEVICE_TO_MODE_TYPE[self.mode_num]
        self.time_boost: int = int(data["time_boost"])
        self.active: bool = data["heating_up"] == "1"
        self.heat_mode: str = self._program_type.heat_mode
        self.temp_mode: str = self._program_type.temp_mode
        self.temperatures: dict[str, Temperature] = {
            temp: Temperature(
                int(data[self._TEMP_TYPE_TO_DEVICE[temp]]),
                is_writable=temp not in self._READONLY_TEMP_TYPES,
                name=temp,
            )
            for temp in self._AVAILABLE_TEMP_TYPES
        }
        self.temperatures[TempType.TARGET] = Temperature(
            None
            if self.temp_mode == "off"
            else self.temperatures[self.temp_mode].device,
            is_writable=False,
            name=TempType.TARGET,
        )

    async def set_temperature(self, temp_type: str, temp_value: int, unit: str):
        """Set a specific temperature for a radiator"""
        if temp_type not in self._TEMP_TYPE_TO_DEVICE:
            raise ApiError(f"Temperature {temp_type} not available.")
        elif temp_type in self._READONLY_TEMP_TYPES:
            raise ApiError(f"Temperature {temp_type} does is read-only.")

        query_params = {}
        query_params["id_device"] = self.id_local
        query_params[Radiator._TEMP_TYPE_TO_DEVICE[temp_type]] = Temperature(
            temp_value, unit
        ).device

        await self._session.write_query(self.home.home_id, query_params)

    async def set_heat_mode(self, heat_mode: str):
        """Set a the heating mode for a radiator"""
        if heat_mode not in self._HEAT_MODE_TO_DEVICE:
            raise ApiError(f"Heating mode {heat_mode} not available.")

        query_params = {}
        query_params["id_device"] = self.id_local
        query_params["gv_mode"] = self._HEAT_MODE_TO_DEVICE[heat_mode]
        query_params["nv_mode"] = self._HEAT_MODE_TO_DEVICE[heat_mode]

        await self._session.write_query(self.home.home_id, query_params)


class TempUnit(StrEnum):
    """Enum of available temperature units."""
    DEVICE = "device"
    CELSIUS = "celsius"
    FARENHEIT = "farenheit"


class Temperature:
    """Models a temperature with device specific unit conversions."""
    def __init__(
        self,
        temperature: Optional[float],
        unit: str = TempUnit.DEVICE,
        *,
        is_writable: bool = False,
        name: str = "(no name)",
    ) -> None:
        self.name: Optional[str] = name
        self.is_writable: bool = is_writable

        if temperature is None:
            self.device: Optional[float] = None
            self.celsius: Optional[float] = None
            self.farenheit: Optional[float] = None
            return None

        if unit == TempUnit.CELSIUS:
            device_temperature = round(18 * temperature + 320)
        elif unit == TempUnit.FARENHEIT:
            device_temperature = round(10 * temperature)
        elif unit == TempUnit.DEVICE:
            device_temperature = round(temperature)
        else:
            raise Exception("Unknown unit")

        self.device = device_temperature
        self.celsius = (device_temperature - 320) / 18
        self.farenheit = device_temperature / 10

    def as_unit(self, unit: str) -> Optional[float]:
        """Return the temperature expressed as the specified unit."""
        if unit == TempUnit.CELSIUS:
            return self.celsius
        if unit == TempUnit.FARENHEIT:
            return self.farenheit
        if unit == TempUnit.DEVICE:
            return self.device
        raise ApiError(f"Unknown temperature unit '{unit}'")

    @classmethod
    def convert(
        cls, temperature: float, from_unit: str, to_unit: str
    ) -> Optional[float]:
        """Convert a temperature between units."""
        return Temperature(temperature, from_unit).as_unit(to_unit)
