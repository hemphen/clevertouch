"""Offline regression tests for API responses."""

from __future__ import annotations

import asyncio
import logging
from json import JSONDecodeError
from unittest.mock import AsyncMock, MagicMock

from aiohttp import ClientResponseError
import pytest

from clevertouch.api import (
    ApiAuthError,
    ApiCallError,
    ApiConnectError,
    ApiSession,
    ApiStatus,
)
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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("replacement", "expected_token"),
    [
        pytest.param({}, "existing-refresh", id="omitted"),
        pytest.param(
            {"refresh_token": "rotated-refresh"}, "rotated-refresh", id="rotated"
        ),
    ],
)
async def test_refresh_token_replacement(
    api: ApiSession,
    monkeypatch: pytest.MonkeyPatch,
    replacement: dict,
    expected_token: str,
) -> None:
    """Retain an omitted refresh token and accept a supplied replacement."""
    api.refresh_token = "existing-refresh"
    monkeypatch.setattr("clevertouch.api.time.time", lambda: 1000)
    response = api._http_session.post.return_value.__aenter__.return_value
    response.status = 200
    response.json = AsyncMock(
        return_value={
            "access_token": "new-access",
            "expires_in": 3600,
            **replacement,
        }
    )

    await api.refresh_openid()

    assert api.refresh_token == expected_token
    assert api.access_token == "new-access"
    assert api.expires_at == 4600
    api._http_session.post.assert_called_once_with(
        api._token_url,
        data={
            "grant_type": "refresh_token",
            "client_id": "app-front",
            "refresh_token": "existing-refresh",
        },
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "replacement",
    [
        pytest.param(None, id="null"),
        pytest.param("", id="empty"),
        pytest.param(123, id="number"),
        pytest.param({}, id="object"),
    ],
)
async def test_invalid_refresh_token_preserves_credentials(
    api: ApiSession, replacement: object
) -> None:
    """Reject malformed replacements without partially updating credentials."""
    api.refresh_token = "existing-refresh"
    api.access_token = "existing-access"
    api.expires_at = 123
    response = api._http_session.post.return_value.__aenter__.return_value
    response.status = 200
    response.json = AsyncMock(
        return_value={
            "access_token": "new-access",
            "refresh_token": replacement,
            "expires_in": 3600,
        }
    )

    with pytest.raises(ApiError, match="Invalid refresh token in token response"):
        await api.refresh_openid()

    assert api.refresh_token == "existing-refresh"
    assert api.access_token == "existing-access"
    assert api.expires_at == 123


@pytest.mark.asyncio
async def test_password_login_does_not_retain_refresh_token(api: ApiSession) -> None:
    """A new password login must not inherit a previous account's token."""
    api.refresh_token = "previous-account-refresh"
    response = api._http_session.post.return_value.__aenter__.return_value
    response.status = 200
    response.json = AsyncMock(return_value={"access_token": "new-account-access"})

    await api.authenticate("offline@example.com", "offline-password")

    assert api.refresh_token is None
    assert api.access_token == "new-account-access"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "operation", ["authenticate", "refresh_openid", "read_user_data"]
)
@pytest.mark.parametrize(
    ("failure_target", "failure", "expected_type"),
    [
        pytest.param(
            "request", asyncio.TimeoutError(), ApiConnectError, id="request-timeout"
        ),
        pytest.param(
            "json", asyncio.TimeoutError(), ApiConnectError, id="body-timeout"
        ),
        pytest.param(
            "json", JSONDecodeError("Invalid JSON", "?", 0), ApiError, id="invalid-json"
        ),
    ],
)
async def test_transport_failure(
    api: ApiSession,
    operation: str,
    failure_target: str,
    failure: Exception,
    expected_type: type[ApiError],
) -> None:
    """Normalize transport failures and leave existing credentials unchanged."""
    api.access_token = "existing-access"
    api.refresh_token = "existing-refresh"
    response = api._http_session.post.return_value.__aenter__.return_value
    response.status = 200
    response.raise_for_status = MagicMock()
    response.json = AsyncMock()
    targets = {"request": api._http_session.post, "json": response.json}
    targets[failure_target].side_effect = failure
    arguments = {
        "authenticate": ("offline@example.com", "offline-password"),
        "refresh_openid": (),
        "read_user_data": (),
    }

    with pytest.raises(expected_type) as error:
        await getattr(api, operation)(*arguments[operation])

    assert type(error.value) is expected_type
    assert error.value.__cause__ is failure
    assert api.access_token == "existing-access"
    assert api.refresh_token == "existing-refresh"
    assert api.expires_at == float("inf")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "operation", ["authenticate", "refresh_openid", "read_user_data"]
)
@pytest.mark.parametrize("failure_target", ["request", "json"])
async def test_transport_cancellation(
    api: ApiSession, operation: str, failure_target: str
) -> None:
    """Cancellation propagates unchanged without modifying credentials."""
    api.access_token = "existing-access"
    api.refresh_token = "existing-refresh"
    response = api._http_session.post.return_value.__aenter__.return_value
    response.status = 200
    response.raise_for_status = MagicMock()
    response.json = AsyncMock()
    cancellation = asyncio.CancelledError()
    targets = {"request": api._http_session.post, "json": response.json}
    targets[failure_target].side_effect = cancellation
    arguments = {
        "authenticate": ("offline@example.com", "offline-password"),
        "refresh_openid": (),
        "read_user_data": (),
    }

    with pytest.raises(asyncio.CancelledError) as error:
        await getattr(api, operation)(*arguments[operation])

    assert error.value is cancellation
    assert api.access_token == "existing-access"
    assert api.refresh_token == "existing-refresh"
    assert api.expires_at == float("inf")


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["_read", "_write"])
@pytest.mark.parametrize(
    ("status", "expected_type"),
    [
        pytest.param(401, ApiAuthError, id="unauthorized"),
        pytest.param(500, ApiConnectError, id="server-error"),
        pytest.param(400, ApiConnectError, id="bad-request"),
        pytest.param(403, ApiConnectError, id="forbidden"),
    ],
)
async def test_api_http_status(
    api: ApiSession, operation: str, status: int, expected_type: type[ApiError]
) -> None:
    """Only HTTP 401 is classified as an API authentication failure."""
    response = api._http_session.post.return_value.__aenter__.return_value
    response.status = status
    response.raise_for_status = MagicMock(
        side_effect=ClientResponseError(
            MagicMock(),
            (),
            status=status,
            message="HTTP error",
        )
    )
    response.json = AsyncMock()

    with pytest.raises(expected_type) as error:
        await getattr(api, operation)("test/", {})

    assert type(error.value) is expected_type
    response.json.assert_not_awaited()
    assert api._http_session.post.call_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["authenticate", "refresh_openid"])
@pytest.mark.parametrize(
    ("status", "expected_type"),
    [
        pytest.param(400, ApiAuthError, id="bad-request"),
        pytest.param(401, ApiAuthError, id="unauthorized"),
        pytest.param(500, ApiError, id="server-error"),
        pytest.param(403, ApiError, id="forbidden"),
    ],
)
async def test_token_failure_logging(
    api: ApiSession,
    caplog: pytest.LogCaptureFixture,
    operation: str,
    status: int,
    expected_type: type[ApiError],
) -> None:
    """Token failure logs apply to both grants without exposing response bodies."""
    api.refresh_token = "private-refresh"
    response = api._http_session.post.return_value.__aenter__.return_value
    response.status = status
    response.json = AsyncMock(return_value={"detail": "private-response"})
    arguments = {
        "authenticate": ("private@example.com", "private-password"),
        "refresh_openid": (),
    }

    with caplog.at_level(logging.DEBUG, logger="clevertouch.api"):
        with pytest.raises(expected_type):
            await getattr(api, operation)(*arguments[operation])

    assert f"Open ID token request failed ({status})" in caplog.messages
    assert "private" not in caplog.text
    response.json.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["authenticate", "refresh_openid"])
async def test_token_success_logging(
    api: ApiSession, caplog: pytest.LogCaptureFixture, operation: str
) -> None:
    """Token success logs describe login and refresh accurately."""
    api.refresh_token = "private-refresh"
    response = api._http_session.post.return_value.__aenter__.return_value
    response.status = 200
    response.json = AsyncMock(
        return_value={
            "access_token": "private-access",
            "refresh_token": "private-rotated",
        }
    )
    arguments = {
        "authenticate": ("private@example.com", "private-password"),
        "refresh_openid": (),
    }

    with caplog.at_level(logging.DEBUG, logger="clevertouch.api"):
        await getattr(api, operation)(*arguments[operation])

    assert "Open ID token request succeeded" in caplog.messages
    assert "private" not in caplog.text
