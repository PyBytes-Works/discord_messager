import pytest
from classes.request_classes import GetRequest


async def test_get_request():
    url = "https://ifconfig.me/all.json"
    spam = GetRequest(url=url)
    answer: dict = await spam._send_request()
    assert answer.get("status") == 200
