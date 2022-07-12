from classes.request_classes import GetRequest


async def test_get_request():
    url = "https://ifconfig.me/all.json"
    spam = GetRequest()
    spam._params = {
        'url': url,
    }
    answer: dict = await spam._send()
    assert answer.get("status") == 200
