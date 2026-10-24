"""Offline regression tests for API responses."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from clevertouch.api import ApiCallError, ApiSession, ApiStatus
from clevertouch.util import ApiError


@pytest.fixture
def api() -> ApiSession:
    """Create an API session with a mocked HTTP transport and valid token."""
    session = MagicMock()
    api = ApiSession(session=session)
    api.expires_at = float("inf")
    return api


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["_read", "_write"])
@pytest.mark.parametrize(
    ("payload", "message", "cause_key"),
    [
        pytest.param(
            {}, "Unexpected JSON format in API response", "code", id="envelope"
        ),
        pytest.param(
            {"code": {}, "data": {}},
            "API status is malformed",
            "code",
            id="status",
        ),
    ],
)
async def test_malformed_response(
    api: ApiSession, operation: str, payload: dict, message: str, cause_key: str
) -> None:
    """Preserve the parsing error and its original cause through reads and writes."""
    response = api._http_session.post.return_value.__aenter__.return_value
    response.raise_for_status = MagicMock()
    response.json = AsyncMock(return_value=payload)

    with pytest.raises(ApiError, match=message) as error:
        await getattr(api, operation)("test/", {})

    assert isinstance(error.value.__cause__, KeyError)
    assert error.value.__cause__.args == (cause_key,)
    response.raise_for_status.assert_called_once_with()


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["_read", "_write"])
async def test_valid_response(api: ApiSession, operation: str) -> None:
    """Accepted responses still return their parsed data and status."""
    response = api._http_session.post.return_value.__aenter__.return_value
    response.raise_for_status = MagicMock()
    response.json = AsyncMock(
        return_value={
            "code": {"code": "8", "key": "ok", "value": "OK"},
            "data": {"accepted": True},
            "parameters": {},
        }
    )

    result = await getattr(api, operation)("test/", {})

    assert result.status == ApiStatus(8, "ok", "OK")
    assert result.data == {"accepted": True}
    assert result.parameters == {}


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["_read", "_write"])
async def test_rejected_response(api: ApiSession, operation: str) -> None:
    """Rejected API statuses still raise the existing call error."""
    response = api._http_session.post.return_value.__aenter__.return_value
    response.raise_for_status = MagicMock()
    response.json = AsyncMock(
        return_value={
            "code": {"code": "0", "key": "rejected", "value": "Rejected"},
            "data": {},
        }
    )

    with pytest.raises(ApiCallError) as error:
        await getattr(api, operation)("test/", {})

    assert error.value.status == ApiStatus(0, "rejected", "Rejected")
