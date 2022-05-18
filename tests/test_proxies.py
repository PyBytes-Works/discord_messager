import aiohttp
import pytest

from fake_data import proxies
from config import PROXY_USER, PROXY_PASSWORD


@pytest.mark.parametrize("sent, received", [items for items in zip(proxies, proxies)])
async def test_send_request(sent, received):
    async with aiohttp.ClientSession() as session:
        url = 'http://superpomerashki.xyz/scripts/my_ip'
        proxy = f"http://{PROXY_USER}:{PROXY_PASSWORD}@{sent}/"
        async with session.get(url=url, proxy=proxy) as response:
            assert await response.text() == received[:-6]
