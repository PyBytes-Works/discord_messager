import json
from random import randint, choice
from base64 import b64encode
from typing import Tuple, Dict

import requests
from python3_anticaptcha import HCaptchaTaskProxyless
from myloguru.my_loguru import get_logger
from pydantic import BaseModel, EmailStr


class UserModel(BaseModel):
    email: EmailStr
    password: str


class TokenGrabber:
    """
    Класс принимает и валидирует е-мэйл и пароль от аккаунта дискорда и
    возвращает словарь с токеном, дискорд_ид и настройками дискорда.
    Автоматически проходит капчу если она требуется.

    Attributes
        email: str
            Will be validated as EmailStr by pydandic

        password: str

        anticaptcha_key: str

        web_url: str

        log_level: int [Optional] = 20
            by default: 20 (INFO)

        proxy: dict [Optional] = None
             example: proxy = {
                "http": "http://user:pass@10.10.1.10:3128/",

                "https": "https://user:pass@10.10.1.10:3128/"

                }
        user_agent: str [Optional] =
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36
        (KHTML, like Gecko) Chrome/101.0.4951.41 Safari/537.36"


    Methods
        get_token
    """

    def __init__(
            self, email: str, password: str, anticaptcha_key: str, web_url: str,
            log_level: int = 20, proxy: dict = None, user_agent: str = ''
    ):
        self.user = UserModel(email=email, password=password)
        self.anticaptcha_key: str = anticaptcha_key
        self.web_url: str = web_url
        self.user_agent: str = user_agent if user_agent else "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.41 Safari/537.36"
        self.session: requests.Session = requests.Session()
        self.fingerprint: str
        self.proxy: dict = proxy if proxy else {}
        self.logger = get_logger(log_level)

    def get_token(self) -> Dict[str, str]:
        self._update_headers()
        self._update_proxy()
        self._update_fingerprint()
        self.session.headers.update({'X-Fingerprint': self.fingerprint})

        return self._get_token_data()

    def _update_proxy(self):
        if self.proxy:
            self.session.proxies.update(self.proxy)

    def _update_headers(self):
        self.logger.debug("Getting headers...")
        self.session.headers.update(
            {'accept': '*/*', 'accept-language': 'ru,en;q=0.9', 'authorization': 'undefined',
             'content-type': 'application/json', 'origin': 'https://discord.com',
             'referer': 'https://discord.com/login', 'user-agent': self.user_agent,
             'x-super-properties': self.__get_xsuperproperties()}
        )
        self.logger.success("Getting headers... OK")

    def _update_fingerprint(self, params: dict = None):
        self.logger.debug("Getting fingerprint...")
        if params is None:
            params = {
                'url': "https://discord.com/api/v9/experiments",
                'verify': False
            }
        try:
            r = self.session.get(**params)
            self.fingerprint = json.loads(r.text)["fingerprint"]
            self.logger.success("Getting fingerprint...OK")
        except KeyError as err:
            self.logger.exception(f'Getting fingerprint...FAIL: {err}')
            raise

    def _get_token_data(self) -> dict:
        self.logger.debug("Getting token...")
        response_text, _ = self._authenticate()
        if 'token' in response_text:
            self.logger.success("Getting token...OK")
            return json.loads(response_text)
        elif 'captcha_sitekey' in response_text:
            self.logger.debug(f'Капча для {self.user.email}, отправляю запрос на решение')
            return self._get_captcha(response_text)
        elif 'The resource is being rate limited' in response_text:
            self.logger.error('Рейт-лимит')
            return {'result': 'rate limit'}
        elif 'ACCOUNT_LOGIN_VERIFICATION_EMAIL' in response_text:
            self.logger.error(f'Требуется подтверждение по почте для {self.user.email}')
            return {'result': 'email secure'}
        else:
            self.logger.error('Ошибка во время решения капчи')
            return {'result': 'captcha error'}

    def _authenticate(self, captcha_key: str = '') -> Tuple[str, int]:
        self.logger.debug("Authenticating...")
        data = {
            'fingerprint': self.fingerprint,
            'email': self.user.email,
            'password': self.user.password
        }
        if captcha_key:
            data.update(captcha_key=captcha_key)
        response = self.session.post(
            url='https://discord.com/api/v9/auth/login',
            json=data,
            verify=False
        )
        status_code = response.status_code
        if status_code == 200:
            self.logger.success("Authenticating...OK")
        else:
            self.logger.error(f"Authenticating...FAIL: {status_code}")
        return response.text, status_code

    def _get_captcha(self, response_text: str) -> Dict[str, str]:
        self.logger.debug("Getting captcha...")
        captcha_sitekey: str = json.loads(response_text)['captcha_sitekey']
        self.logger.debug(f"Response: {response_text}")
        result: dict = (
            HCaptchaTaskProxyless
            .HCaptchaTaskProxyless(anticaptcha_key=self.anticaptcha_key)
            .captcha_handler(websiteURL=self.web_url, websiteKey=captcha_sitekey)
        )
        self.logger.debug(f'Ответ от капчи пришел:\n{result}')
        captcha_key = result.get('solution', {}).get('gRecaptchaResponse', '')

        if not captcha_key:
            self.logger.error("Getting captcha...FAIL")
            return {"result": 'Account authorization key not found in the system'}
        self.logger.success("Getting captcha...OK")
        response_text, status_code = self._authenticate(captcha_key)
        if status_code == 200:
            self.logger.success("Getting token...OK")
            return json.loads(response_text)
        else:
            self.logger.error(f'Невалидная комбинация для {self.user.email}:{self.user.password}')
            return {'result': 'invalid email or password'}

    def __get_xsuperproperties(self) -> bytes:
        browser_vers = f'{randint(10, 99)}.{randint(0, 9)}.{randint(1000, 9999)}.{randint(10, 99)}'
        xsuperproperties = {
            "os": choice(['Windows', 'Linux']), "browser": "Chrome", "device": "",
            "system_locale": choice(['ru', 'en', 'ua']), "browser_user_agent": self.user_agent,
            "browser_version": browser_vers,
            "os_version": choice(['xp', 'vista', '7', '8', '8.1', '10', '11']), "referrer": "",
            "referring_domain": "", "referrer_current": "", "referring_domain_current": "",
            "release_channel": "stable", "client_build_number": "10" + str(randint(1000, 9999)),
            "client_event_source": "null"
        }
        return b64encode(str(xsuperproperties).encode('utf-8'))
