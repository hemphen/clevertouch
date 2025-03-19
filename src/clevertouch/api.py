"""Interface to the cloud API."""

from __future__ import annotations
import logging
from typing import Optional, NamedTuple, Any
from hashlib import md5
from aiohttp import ClientSession, ClientConnectionError, ClientError
import time

from .util import ApiError

_LOGGER = logging.getLogger(__name__)


class ApiStatus(NamedTuple):
    """Status of an API call."""

    code: int
    key: str
    value: str

    def __str__(self) -> str:
        return f"{self.key}({self.code}): {self.value}"

    def __repr__(self) -> str:
        return f"code={self.code}, key={self.key}, value={self.value}"


class ApiResult(NamedTuple):
    """Result of an API call."""

    status: ApiStatus
    data: dict[str, Any]
    parameters: dict[str, Any]


class ApiCallError(ApiError):
    """Exception raised on errors when calling the cloud API."""

    def __init__(self, status: ApiStatus, *args):
        super().__init__(*args)
        self.status: ApiStatus = status


class ApiAuthError(ApiError):
    """Exception raised on authentication errors when calling the cloud API."""


class ApiConnectError(ApiError):
    """Exception raised on connection errors when calling the cloud API."""


class ApiSession:
    """Interface to the cloud API."""

    API_LANG = "en_GB"
    API_PATH = "/api/v0.1/"
    CLIENT_ID = "app-front"

    _DEFAULT_HOST = "e3.lvi.eu"
    _DEFAULT_MANUFACTURER = "purmo"

    def __init__(
        self,
        email: Optional[str] = None,
        refresh_token: Optional[str] = None,
        *,
        host: Optional[str] = None,
        manufacturer: Optional[str] = None,
        session: Optional[ClientSession] = None,
    ) -> None:
        host = host or self._DEFAULT_HOST
        manufacturer = manufacturer or self._DEFAULT_MANUFACTURER
        self._token_url = (
            f"https://auth.{host}/realms/{manufacturer}/protocol/openid-connect/token"
        )
        self._api_base = f"https://{host}{self.API_PATH}"
        self.is_remote_session = session is not None
        self._http_session: ClientSession = session or ClientSession()
        self.email: Optional[str] = email
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = refresh_token
        self.expires_at: float = 0.0

    async def __aenter__(self) -> "ApiSession":
        if self._http_session is None:
            self._http_session = ClientSession()
        return self

    async def __aexit__(self, *excinfo) -> None:
        await self.close()

    async def close(self):
        """Close the connection to the cloud API."""
        if not self.is_remote_session and self._http_session and not self._http_session.closed:
            await self._http_session.close()
            self._http_session = None

    async def authenticate(self, email: str, password: str):
        """Authenticate with the cloud API.
        On success, sets self.access_token, self.refresh_token, self.expires_at.
        """
        self.email = email

        data = {
            "grant_type": "password",
            "client_id": self.CLIENT_ID,
            "username": email,
            "password": password,
        }

        try:
            _LOGGER.debug("Login to openid at '%s' with data '%s'", self._token_url, data)
            async with self._http_session.post(self._token_url, data=data) as response:
                token_data = await self._async_get_token_data(response)
        except ClientError as exc:
            raise ApiConnectError(
                f"Error connecting to {self._token_url}: {exc}"
            ) from exc

        self.access_token = token_data["access_token"]
        self.refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in", 300)  # default 5 min
        self.expires_at = time.time() + expires_in

    async def _async_get_token_data(self, response) -> dict:
        if response.status == 200:
            _LOGGER.debug("Refreshed token successfully")
            return await response.json()
        if response.status==400 or response.status == 401:
            _LOGGER.error("Open ID refresh failed (%s)", response.status)
            raise ApiAuthError("Unauthorized.")
        elif response.status == 500:
            _LOGGER.error("Open ID refresh failed (%s)", response.status)
            raise ApiError("Internal Server Error.")
        else:
            _LOGGER.error("Open ID refresh failed (%s)", response.status)
            raise ApiError(f"Unknown error ({response.status}).")

    async def refresh_openid(self) -> None:
        """Refresh the existing token using the 'refresh_token' grant."""
        if not self.refresh_token:
            raise ApiAuthError("No refresh token stored; cannot refresh.")

        data = {
            "grant_type": "refresh_token",
            "client_id": self.CLIENT_ID,
            "refresh_token": self.refresh_token,
        }
        try:
            async with self._http_session.post(self._token_url, data=data) as response:
                token_data = await self._async_get_token_data(response)
        except ClientError as exc:
            raise ApiConnectError(
                f"Error connecting to {self._token_url}: {exc}"
            ) from exc

        self.access_token = token_data["access_token"]
        self.refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in", 3600)
        self.expires_at = time.time() + expires_in

    async def _ensure_valid_token(self) -> None:
        """Refresh if our token is expired (simple check)."""
        if time.time() >= self.expires_at:
            await self.refresh_openid()

    async def _read(
        self,
        endpoint: str,
        payload: dict,
        *,
        throw_on_error: bool = True,
    ) -> ApiResult:
        result = await self._post(endpoint, payload)
        if throw_on_error:
            if result.status.code not in [1, 8]:
                raise ApiCallError(result.status, f"Read failed with {result.status}")
        return result

    async def _write(
        self,
        endpoint: str,
        payload: dict,
        *,
        throw_on_error: bool = True,
    ) -> ApiResult:
        result = await self._post(endpoint, payload)
        if throw_on_error:
            if result.status.code != 8:
                raise ApiCallError(result.status, f"Write failed with {result.status}")
        return result

    async def read_user_data(self) -> dict[str, Any]:
        """Read account user data from the cloud API."""
        endpoint = "human/user/read/"
        payload = {
            "email": self.email,
        }
        result = await self._read(endpoint, payload)
        return result.data

    async def read_home_data(self, home_id: str) -> dict[str, Any]:
        """Read home data from the cloud API."""
        endpoint = "human/smarthome/read/"
        payload = {
            "smarthome_id": home_id,
        }
        result = await self._read(endpoint, payload)
        return result.data

    async def write_query(self, home_id: str, query_params: dict[str, Any]):
        """Write an update query to the cloud API."""
        endpoint = "human/query/push/"
        payload = {
            "smarthome_id": home_id,
            "context": 1,
            "peremption": 15000,
        }
        for key, value in query_params.items():
            payload[f"query[{key}]"] = value

        return await self._write(endpoint, payload)

    def _parse_api_json(self, json: dict) -> ApiResult:
        try:
            code = json["code"]
            data = json["data"]
            parameters = json.get("parameters")
        except Exception as ex:
            raise ApiError("Unexpected JSON format in API response") from ex

        try:
            code_num = int(code["code"])
            code_key = code["key"]
            code_value = code["value"]
            status = ApiStatus(code_num, code_key, code_value)
        except Exception as ex:
            raise ApiError("API status is malformed") from ex

        return ApiResult(status, data, parameters)

    async def _post(self, endpoint: str, payload: dict | None = None) -> dict:
        """Make an authenticated API request"""
        await self._ensure_valid_token()
        headers = {
            "Authorization": f"Bearer {self.access_token}",
        }

        url = f"{self._api_base}{endpoint.lstrip('/')}"

        try:
            async with self._http_session.post(
                url, data=payload or {}, headers=headers
            ) as resp:
                resp.raise_for_status()
                json_data = await resp.json()
        except ClientError as exc:
            _LOGGER.exception("API request failed: %s", exc)
            raise ApiConnectError(f"API request failed: {exc}") from exc

        try:
            result = self._parse_api_json(json_data)
            _LOGGER.debug("%s called and parsed successfully", endpoint)
        except Exception as ex:
            _LOGGER.exception("Could not parse JSON result from API request")
            result = None

        return result
