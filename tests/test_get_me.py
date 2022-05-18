from fake_data import *
from classes.request_classes import GetMe


async def test_get_token_discord_id():
    counter = 0
    for proxy in proxies:
        result = await GetMe().get_discord_id(token=token, proxy=proxy)
        if result:
            counter += 1
    assert counter == len(proxies)
