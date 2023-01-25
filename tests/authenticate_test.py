import pytest

import os
from dotenv import load_dotenv

load_dotenv()

EMAIL: str = os.getenv('CLEVERTOUCH_EMAIL', '')
PASSWORD: str = os.getenv('CLEVERTOUCH_PASSWORD', '')

from clevertouch.clevertouch import ApiSession

async def authenticate(session: ApiSession):
    await session.authenticate(EMAIL, password = PASSWORD)

def _assert_user_info_set():
    assert EMAIL is not '', "Email missing, set CLEVERTOUCH_EMAIL in the environment or .env"
    assert PASSWORD is not '', "Password missing, set CLEVERTOUCH_PASSWORD in the environment or .env"

@pytest.mark.asyncio
async def test_authentication():
    _assert_user_info_set()
    async with ApiSession() as session:
        try:
            await authenticate(session)
            assert True, "Authentication failed"
        except Exception as ex:
            assert False, f"Authentication failed: {ex}"

@pytest.mark.asyncio
async def test_user_present():
    async with ApiSession() as session:
        await authenticate(session)
        user = await session.get_user()
        assert user.user_id is not None, "No user id found"
