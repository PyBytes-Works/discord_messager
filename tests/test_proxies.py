import aiohttp
import pytest
from tests.conftest import PROXIES, PROXY_USER, PROXY_PASSWORD, PROXY_TEST_URL


@pytest.mark.server
@pytest.mark.parametrize("sent, received", [(sent, received)
                                            for sent, received in zip(PROXIES, PROXIES)])
async def test_all_proxies(sent, received):
    async with aiohttp.ClientSession() as session:
        url = PROXY_TEST_URL
        proxy = f"http://{PROXY_USER}:{PROXY_PASSWORD}@{sent}/"
        async with session.get(url=url, proxy=proxy, timeout=5) as response:
            data = await response.json()
            assert data['ip_addr'] == str(received).split(':')[0]
