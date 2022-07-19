import time

import pytest
from discord_grabber import TokenGrabber


@pytest.mark.local
@pytest.mark.server
async def test_bad_api_key(proxy_data):
    anticaptcha_key = 'bad key'
    email = "aaa@google.com"
    password = "123"
    default_data = dict(email=email, password=password, anticaptcha_key=anticaptcha_key, **proxy_data)
    token_data = await TokenGrabber(**default_data).get_token()
    assert token_data == {'error': 'Task finished with error ERROR_KEY_DOES_NOT_EXIST'}


@pytest.mark.local
@pytest.mark.server
async def test_good_api_key(anticaptcha_key, proxy_data):
    time.sleep(1)
    email = "aaa@google.com"
    password = "123"
    default_data = dict(email=email, password=password, anticaptcha_key=anticaptcha_key, **proxy_data)
    token_grabber = TokenGrabber(**default_data)
    token_grabber._update_headers()
    await token_grabber._update_fingerprint()
    response = await token_grabber._authenticate()
    site_key: str = response.get('captcha_sitekey')
    assert site_key is not None
    assert await token_grabber._get_anticaptcha(site_key)
