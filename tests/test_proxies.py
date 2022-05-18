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
    proxies = (
        "191.101.148.69:45785",
        "50.114.84.57:45785",
        "108.165.218.24:45785",
        "64.137.24.253:45785",
        "185.240.120.61:45785",
        "166.1.8.227:45785",
        "216.162.209.189:45785",
        "45.152.177.17:45785",
        "2.59.60.149:45785",
        "104.227.110.173:45785",
    )
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

