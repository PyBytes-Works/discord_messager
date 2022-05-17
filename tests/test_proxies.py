import asyncio
import datetime

import aiohttp

from classes.request_classes import GetMe
from fake_data import token
from config import PROXY_USER, PROXY_PASSWORD


async def send_request(proxy: str):
    async with aiohttp.ClientSession() as session:
        url = 'https://www.google.com'
        f"http://{PROXY_USER}:{PROXY_PASSWORD}@{proxy}/"
        async with session.get(url) as response:
            return response.status


async def test_all_proxies():

    print("test_all_proxies start")
    counter = 0
    for proxy in proxies:
        t0 = datetime.datetime.now()
        print(f"\nChecking proxy: {proxy} at {t0}")
        # result = await send_request(proxy)
        result = await GetMe().get_discord_id(token=token, proxy=proxy)
        if result:
            counter += 1
        print(f"Result: {result}. Total time: {datetime.datetime.now() - t0}")
    print(f"Total proxies: {len(proxies)}")
    print(f"Working: {counter}")


if __name__ == '__main__':
    proxies = (
        "185.242.85.250:45785",
        "80.82.222.140:45785",
        "46.228.205.187:45785",
        "62.113.216.167:45785",
        "54.38.154.153:45785",
        "185.17.123.31:45785",
        "51.68.178.15:45785",
        "195.54.32.129:45785",
        "51.38.116.213:45785",
        "213.226.71.112:45785",
    )
    try:
        asyncio.new_event_loop().run_until_complete(test_all_proxies())
    except KeyboardInterrupt:
        pass
