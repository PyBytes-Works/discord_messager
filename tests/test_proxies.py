import aiohttp
import pytest

from fake_data import proxies
from config import PROXY_USER, PROXY_PASSWORD


@pytest.mark.parametrize("sent, received", [(sent, received[:-6]) for sent, received in zip(proxies, proxies)])
async def test_all_proxies(sent, received):
    async with aiohttp.ClientSession() as session:
        url = 'http://superpomerashki.xyz/scripts/my_ip'
        proxy = f"http://{PROXY_USER}:{PROXY_PASSWORD}@{sent}/"
        async with session.get(url=url, proxy=proxy) as response:
            assert await response.text() == received


@pytest.mark.parametrize("sent, received", [("185.240.120.61:45785", "185.240.120.61")])
async def test_one_proxy(sent, received):
    async with aiohttp.ClientSession() as session:
        url = 'http://superpomerashki.xyz/scripts/my_ip'
        proxy = f"http://{PROXY_USER}:{PROXY_PASSWORD}@{sent}/"
        async with session.get(url=url, proxy=proxy) as response:
            assert await response.text() == received
