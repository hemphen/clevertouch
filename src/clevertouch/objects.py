"""Provides an object-based abstraction for communicating with the cloud API."""
from __future__ import annotations
from typing import Optional, Any

from .util import ApiError
from .api import ApiSession
from .devices import Device
from .devices.factory import create_device
from .info import HomeInfo


class Account:
    """A represention of an account connected to the cloud API."""

    def __init__(
        self, email: Optional[str] = None, token: Optional[str] = None
    ) -> None:
        self._api_session: ApiSession = ApiSession(email, token)
        self.email: Optional[str] = email
        self.user: Optional[User] = None
        self.homes: dict[str, Home] = {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *excinfo):
        await self.close()

    async def close(self) -> None:
        """Close the connection to the cloud API."""
        await self._api_session.close()

    async def authenticate(
        self,
        email: str,
        password: Optional[str] = None,
        password_hash: Optional[str] = None,
    ) -> None:
        """Authenticate with the cloud API and store credentials."""
        await self._api_session.authenticate(email, password, password_hash)
        self.email = self._api_session.email

    async def get_user(self) -> User:
        """Get user information from the account.

        The user information includes basic information about home(s).
        Does not refresh automatically from the cloud API after first access.
        """
        user = self.user
        if user is None:
            if self.email is None:
                raise ApiError("no email specified")
            user = User(self._api_session, self.email)
            await user.refresh()
        return user

    async def get_home(self, home_id: str) -> Home:
        """Get information for a specific home."""
        home = self.homes.get(home_id)
        if home is None:
            home = Home(self._api_session, home_id)
            await home.refresh()
        return home

    async def get_homes(self) -> list[Home]:
        """Get a list of all homes beloning to the account.

        Does not refresh automatically from the cloud API after first access.
        """
        user = await self.get_user()
        homes: list[Home] = []
        for home_id in user.homes:
            home = await self.get_home(home_id)
            homes.append(home)
        return homes


class Home:
    """A refreshable representation of a home."""

    def __init__(self, api_session: ApiSession, home_id: str) -> None:
        self._api_session = api_session
        self.home_id: str = home_id
        self.info = HomeInfo(home_id=home_id)
        self.devices: dict[str, Device] = {}

    def _update(self, data):
        self.info.update(data)

        for device_data in data["devices"].values():
            device_id = Device.get_id(device_data)
            device = self.devices.get(device_id)
            if device is None:
                self.devices[device_id] = create_device(
                    self._api_session, self.info, device_data
                )
            else:
                device.update(data)

    async def refresh(self) -> None:
        """Refresh the home by calling the cloud API"""
        data = await self._api_session.read_home_data(self.home_id)
        self._update(data)


class User:
    """A refreshable representation of a user."""

    def __init__(self, api_session: ApiSession, email: str) -> None:
        self._api_session = api_session
        self.user_id: Optional[str] = None
        self.email: Optional[str] = email
        self.homes: dict[str, HomeInfo] = {}

    async def refresh(self):
        """Refresh the user by calling the cloud API"""
        data = await self._api_session.read_user_data()
        self._update(data)

    def _update(self, data: dict[str, Any]):
        self.user_id = data["user_id"]
        self.homes = {
            home.home_id: home
            for home in [
                HomeInfo(data=home_data) for home_data in data["smarthomes"].values()
            ]
        }
