import aiohttp
from discord_grabber import TokenGrabber


async def test_bad_api_key():
    anticaptcha_key = 'bad key'
    email = "aaa@google.com"
    password = "123"
    default_data = dict(email=email, password=password, anticaptcha_key=anticaptcha_key)
    token_data = await TokenGrabber(**default_data).get_token()
    assert token_data == {'error': 'Anticaptcha API key error'}


async def test_good_api_key(anticaptcha_key):
    email = "aaa@google.com"
    password = "123"
    default_data = dict(email=email, password=password, anticaptcha_key=anticaptcha_key)
    token_grabber = TokenGrabber(**default_data)
    token_grabber.session = aiohttp.ClientSession(timeout=5)
    token_grabber._update_headers()
    await token_grabber._update_fingerprint()
    response = await token_grabber._authenticate()
    site_key: str = response.get('captcha_sitekey')
    assert site_key is not None
    id_: str = await token_grabber._get_captcha_id(site_key)
    await token_grabber.session.close()
    assert id_ != ''
