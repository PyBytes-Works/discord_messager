from classes.request_classes import GetMe


async def test_get_token_discord_id(token, proxy):
    assert await GetMe().get_discord_id(token=token, proxy=proxy)
