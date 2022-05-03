import asyncio

from classes.request_classes import GetMe
from fake_data import proxies, token


async def test_all_proxies():
    counter = 0
    for proxy in proxies:
        result = await GetMe().get_discord_id(token=token, proxy=proxy)
        print(f"Checking proxy: {proxy}"
              f"\n\tResult: {result}")
        if result:
            counter += 1
    print(f"Total proxies: {len(proxies)}")
    print(f"Working: {counter}")


if __name__ == '__main__':
    try:
        asyncio.new_event_loop().run_until_complete(test_all_proxies())
    except KeyboardInterrupt:
        pass
