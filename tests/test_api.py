"""Offline regression tests for API responses."""

from __future__ import annotations

import asyncio
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


@pytest.mark.asyncio
async def test_concurrent_automatic_refresh(api: ApiSession) -> None:
    """Five expired reads share one refresh before sending requests."""
    api.expires_at = 0
    release_refresh = asyncio.Event()
    started = [asyncio.Event() for _ in range(5)]
    response = api._http_session.post.return_value.__aenter__.return_value
    response.raise_for_status = MagicMock()
    response.json = AsyncMock(
        return_value={
            "code": {"code": "1", "key": "ok", "value": "OK"},
            "data": {},
        }
    )

    async def refresh() -> None:
        await release_refresh.wait()
        api.access_token = "refreshed-access"
        api.expires_at = float("inf")

    api.refresh_openid = AsyncMock(side_effect=refresh)

    async def read(event: asyncio.Event) -> None:
        event.set()
        await api.read_user_data()

    tasks = [asyncio.create_task(read(event)) for event in started]
    try:
        await asyncio.wait_for(asyncio.gather(*(event.wait() for event in started)), 5)
        api._http_session.post.assert_not_called()
        release_refresh.set()
        await asyncio.wait_for(asyncio.gather(*tasks), 5)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    api.refresh_openid.assert_awaited_once_with()
    assert api._http_session.post.call_count == 5
    assert [
        call.kwargs["headers"] for call in api._http_session.post.call_args_list
    ] == [{"Authorization": "Bearer refreshed-access"}] * 5


@pytest.mark.asyncio
async def test_valid_token_skips_refresh(api: ApiSession) -> None:
    """An unexpired token does not trigger automatic refresh."""
    api.refresh_openid = AsyncMock()

    await api._ensure_valid_token()

    api.refresh_openid.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("error_type", [ApiError, asyncio.CancelledError])
async def test_automatic_refresh_failure_recovery(
    api: ApiSession, error_type: type[BaseException]
) -> None:
    """A failed or cancelled refresh releases the lock for the next attempt."""
    api.expires_at = 0
    api.refresh_openid = AsyncMock(side_effect=error_type())

    with pytest.raises(error_type):
        await api._ensure_valid_token()

    async def refresh() -> None:
        api.expires_at = float("inf")

    api.refresh_openid.side_effect = refresh
    await asyncio.wait_for(api._ensure_valid_token(), 5)
    await api._ensure_valid_token()

    assert api.refresh_openid.await_count == 2
