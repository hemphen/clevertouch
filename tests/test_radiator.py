"""Offline regression tests for radiator commands."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from clevertouch.api import ApiSession
from clevertouch.devices.radiator import HeatMode, Radiator, TempType, TempUnit
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
