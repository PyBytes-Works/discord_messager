import aiohttp
import pytest

from data.fake_data import proxies
from config import settings


@pytest.mark.parametrize("sent, received", [(sent, received) for sent, received in zip(proxies, proxies)])
async def test_all_proxies(sent, received):
    async with aiohttp.ClientSession() as session:
        url = settings.BASE_API_URL + '/my_ip'
        proxy = f"http://{settings.PROXY_USER}:{settings.PROXY_PASSWORD}@{sent}/"
        async with session.get(url=url, proxy=proxy) as response:
            assert str(await response.text()) == str(received)


# @pytest.mark.parametrize("sent, received", [("191.101.148.69:45785", "191.101.148.69")])
# async def test_one_proxy(sent, received):
#     async with aiohttp.ClientSession() as session:
#         url = settings.BASE_API_URL + '/my_ip'
#         proxy = f"http://{settings.PROXY_USER}:{settings.PROXY_PASSWORD}@{sent}/"
#         async with session.get(url=url, proxy=proxy) as response:
#             assert await response.text() == received
