import pytest

from classes.request_classes import GetMe


@pytest.mark.local
async def test_get_token_discord_id(token):
    assert await GetMe().get_discord_id(token=token)


@pytest.mark.local
async def test_get_token_discord_id_with_proxy(token, proxy):
    assert await GetMe().get_discord_id(token=token, proxy=proxy)
