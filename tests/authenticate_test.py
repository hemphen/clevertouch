import pytest
import os
from dotenv import load_dotenv

from clevertouch import Account

load_dotenv()

EMAIL: str = os.getenv("CLEVERTOUCH_EMAIL", "")
PASSWORD: str = os.getenv("CLEVERTOUCH_PASSWORD", "")


async def _authenticate(session: Account):
    await session.authenticate(EMAIL, password=PASSWORD)


def _assert_user_info_set():
    assert (
        EMAIL is not ""
    ), "Email missing, set CLEVERTOUCH_EMAIL in the environment or .env"
    assert (
        PASSWORD is not ""
    ), "Password missing, set CLEVERTOUCH_PASSWORD in the environment or .env"


@pytest.mark.asyncio
async def test_authentication():
    """Test if authentication to the cloud API is successful"""
    _assert_user_info_set()
    async with Account() as session:
        await _authenticate(session)
        assert True, "Authentication failed"


@pytest.mark.asyncio
async def test_user_present():
    """Test if the account contains a user"""
    async with Account() as session:
        await _authenticate(session)
        user = await session.get_user()
        assert user.user_id is not None, "No user id found"
