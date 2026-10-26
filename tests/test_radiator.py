"""Offline regression tests for radiator commands."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from clevertouch.api import ApiSession
from clevertouch.devices.radiator import (
    HeatMode,
    Radiator,
    Temperature,
    TempType,
    TempUnit,
)
from clevertouch.info import HomeInfo
from clevertouch.util import ApiError


@pytest.fixture
def radiator() -> Radiator:
    """Create a radiator with known temperatures and boost settings."""
    home = HomeInfo(
        data={
            "smarthome_id": "home",
            "label": "Home",
            "zones": [{"num_zone": "1", "zone_label": "Room"}],
        }
    )
    session = MagicMock(spec=ApiSession)
    session.write_query = AsyncMock()
    return Radiator(
        session,
        home,
        {
            "id": "radiator",
            "id_device": "2",
            "label_interface": "Radiator",
            "num_zone": "1",
            "gv_mode": "0",
            "heating_up": "1",
            "consigne_eco": "590",
            "consigne_hg": "446",
            "consigne_confort": "698",
            "temperature_air": "680",
            "consigne_boost": "752",
            "time_boost": "300",
            "time_boost_format_chrono": {"m": "2", "s": "30"},
        },
    )


@pytest.mark.asyncio
async def test_activation_failure_preserves_state(radiator: Radiator) -> None:
    """A rejected activation leaves all exposed radiator state unchanged."""
    before = vars(radiator).copy()
    before["temperatures"] = radiator.temperatures.copy()
    error = ApiError("Write rejected")
    radiator._session.write_query.side_effect = error

    with pytest.raises(ApiError, match="Write rejected") as raised:
        await radiator.activate_mode(
            HeatMode.BOOST, temp_value=25, temp_unit=TempUnit.CELSIUS, boost_time=600
        )

    assert raised.value is error
    assert vars(radiator) == before


@pytest.mark.asyncio
async def test_activation_cancellation_preserves_state(radiator: Radiator) -> None:
    """Cancellation during the write leaves temperatures and boost untouched."""
    started = asyncio.Event()
    temperatures = radiator.temperatures.copy()

    async def write_query(home_id: str, query_params: dict) -> None:
        started.set()
        await asyncio.Future()

    radiator._session.write_query.side_effect = write_query
    task = asyncio.create_task(
        radiator.activate_mode(
            HeatMode.BOOST, temp_value=25, temp_unit=TempUnit.CELSIUS, boost_time=600
        )
    )
    await started.wait()
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert radiator.temperatures == temperatures
    assert radiator.boost_time == 300
    assert radiator.boost_remaining == 150
    assert radiator.heat_mode == HeatMode.COMFORT
    assert radiator.temp_type == TempType.COMFORT
    assert radiator.active is True


@pytest.mark.asyncio
async def test_activation_success(radiator: Radiator) -> None:
    """An accepted activation retains the command and optimistic updates."""
    await radiator.activate_mode(
        HeatMode.BOOST, temp_value=25, temp_unit=TempUnit.CELSIUS, boost_time=600
    )

    radiator._session.write_query.assert_awaited_once_with(
        "home",
        {
            "id_device": "2",
            "gv_mode": "4",
            "nv_mode": "4",
            "consigne_boost": 770,
            "time_boost": 600,
        },
    )
    assert radiator.temperatures[TempType.BOOST].celsius == 25
    assert radiator.temperatures[TempType.TARGET].celsius == 25
    assert radiator.boost_time == 600
    assert radiator.boost_remaining == 600
    assert radiator.heat_mode == HeatMode.BOOST
    assert radiator.temp_type == TempType.BOOST
    target = radiator.temperatures[TempType.TARGET]
    preset = radiator.temperatures[TempType.BOOST]
    assert target is not preset
    assert target.name == TempType.TARGET
    assert target.is_writable is False
    assert preset.name == TempType.BOOST
    assert preset.is_writable is True
    assert radiator.active is True


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["set_heat_mode", "activate_mode"])
@pytest.mark.parametrize(
    ("initial_mode", "mode", "temp_type", "target", "device_mode"),
    [
        pytest.param(
            HeatMode.COMFORT, HeatMode.ECO, TempType.ECO, 15, "3", id="comfort-to-eco"
        ),
        pytest.param(
            HeatMode.ECO, HeatMode.OFF, TempType.NONE, None, "1", id="eco-to-off"
        ),
        pytest.param(
            HeatMode.COMFORT, HeatMode.PROGRAM, TempType.ECO, 15, "11", id="program"
        ),
    ],
)
async def test_mode_change_state(
    radiator: Radiator,
    operation: str,
    initial_mode: HeatMode,
    mode: HeatMode,
    temp_type: TempType,
    target: float | None,
    device_mode: str,
) -> None:
    """Accepted mode commands expose a consistent local mode and target."""
    await radiator.set_heat_mode(initial_mode)
    radiator._session.write_query.reset_mock()

    await getattr(radiator, operation)(mode)

    radiator._session.write_query.assert_awaited_once_with(
        "home", {"id_device": "2", "gv_mode": device_mode, "nv_mode": device_mode}
    )
    assert radiator.heat_mode == mode
    assert radiator.temp_type == temp_type
    assert radiator.temperatures[TempType.TARGET].celsius == target
    assert radiator.temperatures[TempType.TARGET].name == TempType.TARGET
    assert radiator.temperatures[TempType.TARGET].is_writable is False
    assert radiator.active is True


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["set_heat_mode", "activate_mode"])
@pytest.mark.parametrize("error_type", [ApiError, asyncio.CancelledError])
async def test_mode_change_failure(
    radiator: Radiator, operation: str, error_type: type[BaseException]
) -> None:
    """Rejected or cancelled mode commands preserve local state."""
    before = vars(radiator).copy()
    before["temperatures"] = radiator.temperatures.copy()
    radiator._session.write_query.side_effect = error_type()

    with pytest.raises(error_type):
        await getattr(radiator, operation)(HeatMode.ECO)

    assert vars(radiator) == before


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("arguments", "extra_payload", "target", "boost_time", "boost_remaining"),
    [
        pytest.param({}, {}, 24, 300, 150, id="omitted"),
        pytest.param(
            {"temp_value": 0, "temp_unit": TempUnit.CELSIUS},
            {"consigne_boost": 320},
            0,
            300,
            150,
            id="zero-temperature",
        ),
        pytest.param(
            {"boost_time": 0},
            {"time_boost": 0},
            24,
            0,
            0,
            id="zero-boost-time",
        ),
    ],
)
async def test_activation_optional_arguments(
    radiator: Radiator,
    arguments: dict,
    extra_payload: dict,
    target: float,
    boost_time: int,
    boost_remaining: int,
) -> None:
    """Distinguish omitted arguments from supplied zero values."""
    await radiator.activate_mode(HeatMode.BOOST, **arguments)

    radiator._session.write_query.assert_awaited_once_with(
        "home",
        {"id_device": "2", "gv_mode": "4", "nv_mode": "4", **extra_payload},
    )
    assert radiator.temperatures[TempType.BOOST].celsius == target
    assert radiator.temperatures[TempType.TARGET].celsius == target
    assert radiator.boost_time == boost_time
    assert radiator.boost_remaining == boost_remaining


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mode", "arguments", "message"),
    [
        pytest.param(
            HeatMode.BOOST,
            {"temp_value": 0},
            "Unit must be set when a temp value is provided.",
            id="missing-unit",
        ),
        pytest.param(
            HeatMode.OFF,
            {"temp_value": 0, "temp_unit": TempUnit.CELSIUS},
            "Temperature can not be set for Off.",
            id="incompatible-temperature",
        ),
        pytest.param(
            HeatMode.ECO,
            {"boost_time": 0},
            "Boost time can only be set for boost mode.",
            id="incompatible-boost-time",
        ),
    ],
)
async def test_activation_zero_validation(
    radiator: Radiator, mode: HeatMode, arguments: dict, message: str
) -> None:
    """Validate supplied zero values before writing or changing local state."""
    before = vars(radiator).copy()
    before["temperatures"] = radiator.temperatures.copy()

    with pytest.raises(ApiError) as error:
        await radiator.activate_mode(mode, **arguments)

    assert str(error.value) == message
    radiator._session.write_query.assert_not_awaited()
    assert vars(radiator) == before


@pytest.mark.parametrize("unit", ["fahrenheit", "farenheit", TempUnit.FARENHEIT])
def test_fahrenheit_spelling(unit: str) -> None:
    """Accept the deprecated spelling alongside the correct one."""
    temp = Temperature(68, unit)
    assert temp.device == 680
    assert temp.fahrenheit == 68
    assert temp.farenheit == 68
    assert temp.as_unit(unit) == 68
    assert TempUnit.FAHRENHEIT == "fahrenheit"
