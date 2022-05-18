from classes.request_classes import GetRequest


async def test_get_request():
    url = 'http://superpomerashki.xyz/scripts/my_ip'
    spam = GetRequest()
    spam._params = {
        'url': url,
    }
    answer: dict = await spam._send()
    assert answer.get("status") == 200


async def test_get_request_wrong_url():
    url = 'http://superpomerashki.xyz/scripts/my_i'
    spam = GetRequest()
    spam._params = {
        'url': url,
    }
    answer: dict = await spam._send()
    assert answer.get("status") == 404
