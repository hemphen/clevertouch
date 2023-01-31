"""Interface to the cloud API."""
from __future__ import annotations
import logging
from typing import Optional, NamedTuple, Any
from hashlib import md5
from aiohttp import ClientSession, ClientConnectionError, ClientError

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
    API_BASE = "https://e3.lvi.eu"
    API_PATH = "/api/v0.1/"

    def __init__(
        self, email: Optional[str] = None, token: Optional[str] = None
    ) -> None:
        self._http_session: ClientSession = ClientSession(self.API_BASE)
        self.email: Optional[str] = email
        self.token: Optional[str] = token

    async def __aenter__(self):
        return self

    async def __aexit__(self, *excinfo):
        await self.close()

    async def close(self):
        """Close the connection to the cloud API."""
        await self._http_session.close()

    async def authenticate(
        self,
        email: str,
        password: Optional[str] = None,
        password_hash: Optional[str] = None,
    ):
        """Authenticate with the cloud API."""
        self.email = email
        if password_hash is None or password_hash == "":
            if password is None:
                raise ApiError("No password provided")
            password_hash = md5(password.encode()).hexdigest().encode().decode()

        endpoint = "human/user/auth/"
        payload = {
            "email": email,
            "password": password_hash,
            "remember_me": "true",
            "lang": self.API_LANG,
        }

        result = await self._post(endpoint, payload, authenticate=False)

        status = result.status
        if status.key != "OK":
            if status.key == "ERR_ROUTE":
                raise ApiConnectError(status)
            if status.key == "ERR_PARAM":
                raise ApiAuthError("Invalid email or password")
            raise ApiCallError(status, "Authentication failed %s", status)

        self.email = result.data["user_infos"]["email"]
        self.token = result.data["token"]

    async def _read(
        self,
        endpoint: str,
        payload: dict,
        *,
        authenticate: bool = True,
        throw_on_error: bool = True,
    ) -> ApiResult:
        result = await self._post(endpoint, payload, authenticate=authenticate)
        if throw_on_error:
            if result.status.code != 1:
                raise ApiCallError(result.status, f"Read failed with {result.status}")
        return result

    async def _write(
        self,
        endpoint: str,
        payload: dict,
        *,
        authenticate: bool = True,
        throw_on_error: bool = True,
    ) -> ApiResult:
        result = await self._post(endpoint, payload, authenticate=authenticate)
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
        _, data, _ = await self._read(endpoint, payload)
        return data

    async def read_home_data(self, home_id: str) -> dict[str, Any]:
        """Read home data from the cloud API."""
        endpoint = "human/smarthome/read/"
        payload = {
            "smarthome_id": home_id,
        }
        _, data, _ = await self._read(endpoint, payload)
        return data

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
            parameters = json["parameters"]
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

    async def _post(
        self, endpoint: str, payload: dict[str, Any], *, authenticate: bool
    ) -> ApiResult:
        if authenticate:
            payload.update(
                {
                    "token": self.token,
                    "lang": self.API_LANG,
                }
            )

        try:
            async with self._http_session.post(
                self.API_PATH + endpoint, data=payload
            ) as response:
                response.raise_for_status()
                json_data = await response.json()
        except ClientConnectionError as ex:
            raise ApiConnectError(f"Connection error - {ex}") from ex
        except ClientError as ex:
            raise ApiConnectError(f"Unexpected cloud API error - {ex}") from ex

        result = self._parse_api_json(json_data)

        _LOGGER.debug(
            "%s called with status %s (%s): %s",
            endpoint,
            result.status.key,
            result.status.code,
            result.status.value,
        )

        return result
