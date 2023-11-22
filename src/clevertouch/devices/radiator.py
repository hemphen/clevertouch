"""Models a radiator."""
from __future__ import annotations
from typing import Optional, Any, NamedTuple

from .. import ApiSession, ApiError
from ..info import HomeInfo
from ..util import StrEnum

from .device import Device
from .const import DeviceType, DeviceTypeId


class _ModeInfo(NamedTuple):
    heat_mode: HeatMode
    temp_type: TempType


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
        "2": _ModeInfo(HeatMode.FROST, TempType.FROST),
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
        HeatMode.BOOST: "4",
        HeatMode.OFF: "1",
    }

    _HEAT_MODE_TO_WRITABLE_TEMP_TYPE: dict[str, str] = {
        HeatMode.ECO: TempType.ECO,
        HeatMode.FROST: TempType.FROST,
        HeatMode.COMFORT: TempType.COMFORT,
        HeatMode.BOOST: TempType.BOOST,
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
    ]

    _AVAILABLE_HEAT_MODES: list[str] = [
        HeatMode.COMFORT,
        HeatMode.ECO,
        HeatMode.FROST,
        HeatMode.PROGRAM,
        HeatMode.BOOST,
        HeatMode.OFF,
    ]

    def __init__(self, session: ApiSession, home: HomeInfo, data: dict) -> None:
        super().__init__(
            session,
            home,
            data,
            DeviceType.RADIATOR,
            DeviceTypeId.RADIATOR,
            do_update=False,
        )
        self.modes: list[str] = self._AVAILABLE_HEAT_MODES
        self.active: bool = False
        self.heat_mode = HeatMode.OFF
        self.temp_type = TempType.NONE
        self.boost_time: int = 0
        self.boost_remaining: int = 0
        self.temperatures: dict[str, Temperature] = {}
        self.update(data)

    def update(self, data: dict[str, Any]):
        """Update the radiator from cloud API data."""
        super().update(data)
        mode_num = data["gv_mode"]
        program_type = self._DEVICE_TO_MODE_TYPE[mode_num]
        self.active = data["heating_up"] == "1"
        self.heat_mode = program_type.heat_mode
        self.temp_type = program_type.temp_type
        self.temperatures = {
            temp: Temperature(
                int(data[self._TEMP_TYPE_TO_DEVICE[temp]]),
                is_writable=temp not in self._READONLY_TEMP_TYPES,
                name=temp,
            )
            for temp in self._AVAILABLE_TEMP_TYPES
        }
        self.temperatures[TempType.TARGET] = Temperature(
            None
            if self.temp_type == TempType.NONE
            else self.temperatures[self.temp_type].device,
            is_writable=False,
            name=TempType.TARGET,
        )
        # Read boost settings
        # 'boost_time' is the user writable boost time
        self.boost_time = int(data.get("time_boost") or 0)
        # 'time_boost_format_chrono' holds remaining boost time with higher resolution
        node = data.get("time_boost_format_chrono")
        if node:
            self.boost_remaining = (
                int(node.get("d") or 0) * 24 * 60 * 60
                + int(node.get("h") or 0) * 60 * 60
                + int(node.get("m") or 0) * 60
                + int(node.get("s") or 0)
            )
        else:
            self.boost_remaining = None

    async def set_temperature(self, temp_type: str, temp_value: float, unit: str):
        """Set a specific temperature for a radiator"""
        if temp_type not in self._TEMP_TYPE_TO_DEVICE:
            raise ApiError(f"Temperature {temp_type} not available.")
        elif temp_type in self._READONLY_TEMP_TYPES:
            raise ApiError(f"Temperature {temp_type} is read-only.")

        new_temp = Temperature(temp_value, unit, is_writable=True, name=temp_type)

        query_params = {}
        query_params["id_device"] = self.id_local
        query_params[Radiator._TEMP_TYPE_TO_DEVICE[temp_type]] = new_temp.device

        await self._session.write_query(self.home.home_id, query_params)

        # This is debatable - for some scenarios it is reasonable to
        # update the value in the current object with the assumed
        # change, for others not
        self.temperatures[temp_type] = new_temp

        # To further complicate. If the temp_type set is the same type
        # that the object currently targets, that value should be updated as well
        if temp_type == self.temp_type:
            self.temperatures[TempType.TARGET] = Temperature(
                new_temp.device,
                is_writable=False,
                name=TempType.TARGET,
            )

    async def set_heat_mode(self, heat_mode: str):
        """Set a the heating mode for a radiator"""
        if heat_mode not in self._HEAT_MODE_TO_DEVICE:
            raise ApiError(f"Heating mode {heat_mode} not available.")

        query_params = {}
        query_params["id_device"] = self.id_local
        query_params["gv_mode"] = self._HEAT_MODE_TO_DEVICE[heat_mode]
        query_params["nv_mode"] = self._HEAT_MODE_TO_DEVICE[heat_mode]

        await self._session.write_query(self.home.home_id, query_params)

        # Debatable - see set_temperature
        self.heat_mode = heat_mode

    async def set_boost_time(self, boost_time: int) -> None:
        """Set default boost time for subsequent activations of boost mode"""

        query_params = {}
        query_params["id_device"] = self.id_local
        query_params["time_boost"] = boost_time

        await self._session.write_query(self.home.home_id, query_params)

        # Debatable - see set_temperature
        self.boost_time = boost_time

    async def activate_mode(
        self,
        heat_mode: str,
        *,
        temp_value: Optional[float] = None,
        temp_unit: Optional[str] = None,
        boost_time: Optional[int] = None,
    ) -> None:
        """
        Set the heating mode, optionally adjusting parameters.

        Parameters:
        heat_mode : str
            Heat mode to activate. Should be one of the `HeatMode` constants.
        temp_value : float, optional
            Temperature value. Must be used together with `temp_unit`.
        temp_unit : str, optional
            Unit of `temp_value`. Should be `celsius`, `farenheit` or `device`.
        boost_time : int, optional
            Length of period that boost mode should be active, in seconds.
            Applicable to `HeatMode.Boost` only.

        Raises:
        ApiError
            If any of the arguments are invalid or incompatible.
        """

        if heat_mode not in self._HEAT_MODE_TO_DEVICE:
            raise ApiError(f"Heating mode {heat_mode} not available.")
        if temp_value and not temp_unit:
            raise ApiError("Unit must be set when a temp value is provided.")
        if temp_value and heat_mode not in self._HEAT_MODE_TO_WRITABLE_TEMP_TYPE:
            raise ApiError(f"Temperature can not be set for {heat_mode}.")
        if boost_time and heat_mode != HeatMode.BOOST:
            raise ApiError("Boost time can only be set for boost mode.")

        query_params = {}
        query_params["id_device"] = self.id_local
        query_params["gv_mode"] = self._HEAT_MODE_TO_DEVICE[heat_mode]
        query_params["nv_mode"] = self._HEAT_MODE_TO_DEVICE[heat_mode]

        if temp_value and temp_unit:
            temp_type = self._HEAT_MODE_TO_WRITABLE_TEMP_TYPE[heat_mode]
            new_temp = Temperature(
                temp_value, temp_unit, is_writable=True, name=temp_type
            )
            query_params[self._TEMP_TYPE_TO_DEVICE[temp_type]] = new_temp.device
            # Debatable - see set_temperature
            self.temperatures[temp_type] = new_temp
            self.temperatures[TempType.TARGET] = new_temp

        if boost_time:
            query_params["time_boost"] = boost_time
            # Debatable - see set_temperature
            self.boost_time = boost_time
            self.boost_remaining = boost_time

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
            raise KeyError(f"Unknown unit: {unit}")

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
