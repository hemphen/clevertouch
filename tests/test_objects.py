"""Offline regression tests for account caching."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from clevertouch.objects import Account
from clevertouch.util import ApiError


@pytest.fixture
def account() -> Account:
    """Create an account with mocked reads and no network access."""
    account = Account("first@example.com", session=MagicMock())
    account.api.read_user_data = AsyncMock(
        return_value={
            "user_id": "first-user",
            "smarthomes": [{"smarthome_id": "home", "label": "Home"}],
        }
    )
    account.api.read_home_data = AsyncMock(
        return_value={
            "smarthome_id": "home",
            "label": "Home",
            "devices": [],
        }
    )
    account.api.authenticate = AsyncMock()
    return account


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("getter", "arguments", "read_method"),
    [
        pytest.param("get_user", (), "read_user_data", id="user"),
        pytest.param("get_home", ("home",), "read_home_data", id="home"),
    ],
)
async def test_cached_getter_and_explicit_refresh(
    account: Account, getter: str, arguments: tuple, read_method: str
) -> None:
    """Repeated getters reuse objects; an explicit refresh performs another read."""
    first = await getattr(account, getter)(*arguments)
    second = await getattr(account, getter)(*arguments)
    read = getattr(account.api, read_method)

    assert second is first
    assert read.await_count == 1

    await first.refresh()

    assert read.await_count == 2
    assert await getattr(account, getter)(*arguments) is first
    assert read.await_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("getter", "arguments", "read_method"),
    [
        pytest.param("get_user", (), "read_user_data", id="user"),
        pytest.param("get_home", ("home",), "read_home_data", id="home"),
    ],
)
@pytest.mark.parametrize(
    ("failure", "error_type"),
    [
        pytest.param(ApiError("Read failed"), ApiError, id="read-error"),
        pytest.param({}, KeyError, id="parse-error"),
    ],
)
async def test_failed_initial_fetch_not_cached(
    account: Account,
    getter: str,
    arguments: tuple,
    read_method: str,
    failure: object,
    error_type: type[Exception],
) -> None:
    """Failed reads and parsing errors do not cache partially initialized objects."""
    read = getattr(account.api, read_method)
    read.side_effect = [failure, read.return_value]

    with pytest.raises(error_type):
        await getattr(account, getter)(*arguments)

    assert account.user is None
    assert account.homes == {}

    fetched = await getattr(account, getter)(*arguments)
    assert read.await_count == 2
    assert await getattr(account, getter)(*arguments) is fetched
    assert read.await_count == 2


@pytest.mark.asyncio
async def test_get_homes_reuses_cached_objects(account: Account) -> None:
    """The list getter reuses homes fetched by either getter."""
    user = await account.get_user()
    home = await account.get_home("home")

    assert await account.get_homes() == [home]
    assert await account.get_homes() == [home]
    assert account.user is user
    assert account.homes == {"home": home}
    account.api.read_user_data.assert_awaited_once_with()
    account.api.read_home_data.assert_awaited_once_with("home")


@pytest.mark.asyncio
async def test_authentication_clears_caches(account: Account) -> None:
    """Successful authentication discards cached objects from the previous account."""
    old_user = await account.get_user()
    old_home = await account.get_home("home")
    account.api.email = "second@example.com"

    await account.authenticate("second@example.com", "offline-password")

    assert account.email == "second@example.com"
    assert account.user is None
    assert account.homes == {}
    account.api.authenticate.assert_awaited_once_with(
        "second@example.com", "offline-password"
    )

    account.api.read_user_data.return_value = {
        "user_id": "second-user",
        "smarthomes": [],
    }
    user = await account.get_user()
    home = await account.get_home("home")

    assert user is not old_user
    assert user.user_id == "second-user"
    assert user.email == "second@example.com"
    assert home is not old_home
    assert account.api.read_user_data.await_count == 2
    assert account.api.read_home_data.await_count == 2


@pytest.mark.asyncio
async def test_failed_authentication_preserves_caches(account: Account) -> None:
    """A failed authentication does not discard the existing cached objects."""
    user = await account.get_user()
    home = await account.get_home("home")
    account.api.authenticate.side_effect = ApiError("Login failed")

    with pytest.raises(ApiError, match="Login failed"):
        await account.authenticate("second@example.com", "offline-password")

    assert account.email == "first@example.com"
    assert await account.get_user() is user
    assert await account.get_home("home") is home
    account.api.read_user_data.assert_awaited_once_with()
    account.api.read_home_data.assert_awaited_once_with("home")
