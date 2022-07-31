import pytest
from anticaptchaofficial.recaptchav2proxyless import *


@pytest.mark.local
@pytest.mark.server
async def test_bad_api_key(anticaptcha_key):
    solver = recaptchaV2Proxyless()
    solver.set_verbose(1)
    solver.set_key('123')
    with pytest.raises(KeyError):
        solver.get_balance()


@pytest.mark.local
@pytest.mark.server
async def test_good_api_key(anticaptcha_key):
    solver = recaptchaV2Proxyless()
    solver.set_verbose(1)
    solver.set_key(anticaptcha_key)
    balance = solver.get_balance()
    assert balance > 0
