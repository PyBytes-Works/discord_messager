import asyncio

from random import randint, choice
from typing import Dict, Optional

import aiohttp
import fake_useragent
from myloguru.my_loguru import get_logger
from pydantic import BaseModel, EmailStr


class UserModel(BaseModel):
    email: EmailStr
    password: str


class CaptchaTimeoutError(Exception):
    def __str__(self):
        return "Captcha time is over. Please try later..."


class CaptchaIDError(Exception):
    def __str__(self):
        return "Captcha ID error"


class RequestError(Exception):
    def __str__(self):
        return "Request error"


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

        proxy: str [Optional] = ''
             example: proxy = "http://user:pass@10.10.1.10:3128/"

        user_agent: str [Optional] =
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36
        (KHTML, like Gecko) Chrome/101.0.4951.41 Safari/537.36"

        logger=None
            By default will be used my_loguru logger by Deskent

            (pip install myloguru-deskent)

        max_tries: int = 12
            Maximum amount of tries for getting captcha.
            Delay between tries 10 seconds.

    Methods
        get_token
    """

    def __init__(
            self, email: str, password: str, anticaptcha_key: str, web_url: str,
            log_level: int = 20, proxy: str = '', user_agent: str = '', logger=None,
            max_tries: int = 12
    ):
        self.session: Optional[aiohttp.ClientSession] = None
        self.user = UserModel(email=email, password=password)
        self.anticaptcha_key: str = anticaptcha_key
        self.web_url: str = web_url
        self.user_agent: str = (
            user_agent
            if user_agent
            else fake_useragent.UserAgent(path='./useragent.json', verify_ssl=False)['google chrome']
        )
        self.headers: dict = {}
        self.fingerprint: str
        self.proxy: str = proxy
        self.max_tries: int = max_tries
        self.pause: int = 10
        self.logger = logger if logger else get_logger(log_level)

    async def get_token(self) -> Dict[str, str]:
        """
        :return: dict: {'token': '...'} if no errors else {''errors}
        """
        async with aiohttp.ClientSession() as session:
            self.session: aiohttp.ClientSession = session
            self._update_headers()
            await self._update_fingerprint()
            self.headers.update({'X-Fingerprint': self.fingerprint})
            try:
                return await self._get_token_data()
            except (CaptchaTimeoutError, CaptchaIDError, RequestError) as err:
                error_text = f'{err}'
            self.logger.error(error_text)

            return {'error': error_text}

    def _update_headers(self):
        self.logger.debug("Getting headers...")
        self.headers.update(
            {'accept': '*/*', 'accept-language': 'ru,en;q=0.9', 'authorization': 'undefined',
             'content-type': 'application/json', 'origin': 'https://discord.com',
             'referer': 'https://discord.com/login', 'user-agent': self.user_agent,
             'x-super-properties': self.__get_xsuperproperties()}
        )
        self.logger.success("Getting headers... OK")

    async def _update_fingerprint(self, params: dict = None):
        self.logger.debug("Getting fingerprint...")
        if params is None:
            params = {
                'url': "https://discord.com/api/v9/experiments",
                'headers': self.headers
            }
        response: dict = await self._send_request(params)
        self.fingerprint = response.get("fingerprint")
        if not self.fingerprint:
            self.logger.exception(f'Getting fingerprint... FAIL')
            raise ValueError("No fingerprint")
        self.logger.success("Getting fingerprint... OK")

    async def _get_token_data(self) -> dict:

        self.logger.debug("Getting token...")
        response: dict = await self._authenticate()
        self.logger.debug(f"Authenticate response: {response}")
        if response.get('token'):
            self.logger.success("Getting token...OK")
            return response
        elif response.get('captcha_sitekey'):
            self.logger.debug(f'Капча для {self.user.email}, отправляю запрос на решение')
            captcha_key: str = await self._get_captcha_token(response.get('captcha_sitekey'))
            response: dict = await self._authenticate(captcha_key)
        self.logger.debug(f"Captcha authenticate response: {response}")
        response_text = str(response)
        if 'token' in response_text:
            self.logger.success("Getting token...OK")
            return response
        elif 'INVALID_LOGIN' in response_text:
            error_text = f'Неверная пара Email-пароль: {self.user.email}:{self.user.password}'
        elif 'The resource is being rate limited' in response_text:
            error_text = 'The resource is being rate limited'
        elif 'ACCOUNT_LOGIN_VERIFICATION_EMAIL' in response_text:
            error_text = f'Требуется подтверждение по почте для {self.user.email}'
        else:
            error_text = f'Undefined error: {response_text}'
        self.logger.error(error_text)

        return {'error': error_text}

    async def _authenticate(self, captcha_key: str = '') -> dict:
        self.logger.debug("Authenticating...")
        data = {
            'fingerprint': self.fingerprint,
            'email': self.user.email,
            'password': self.user.password
        }
        if captcha_key:
            data.update(captcha_key=captcha_key)
            self.logger.debug(f"_authenticate data:\n{data}")
        params = dict(
            url='https://discord.com/api/v9/auth/login',
            headers=self.headers,
            json=data,
        )
        response: dict = await self._send_request(params=params, method='post')
        if response:
            self.logger.success("Authenticating...OK")
        else:
            self.logger.error(f"Authenticating...FAIL: {response}")

        return response

    async def _send_request(self, params: dict, method: str = 'get') -> dict:
        if self.proxy:
            params.update(proxy=self.proxy)
        params.update(ssl=False)
        async with self.session.request(method=method, **params) as response:
            try:
                return await response.json()
            except Exception as err:
                self.logger.exception(err)
                response_text: str = await response.text()
                self.logger.debug(response_text)
                raise RequestError

        return {}

    async def __get_captcha_token(self, site_key: str) -> str:

        url = (
            f"http://2captcha.com/in.php?key={self.anticaptcha_key}"
            f"&method=hcaptcha"
            f"&sitekey={site_key}"
            f"&pageurl=https://discord.com/login&json=1"
        )
        response_id: dict = await self._send_request(params=dict(url=url))
        id: str = response_id.get("request", '')
        if not id:
            raise CaptchaIDError
        url = (
            f"http://2captcha.com/res.php?key={self.anticaptcha_key}"
            f"&action=get"
            f"&json=1"
            f"&id={id}"
        )
        self.logger.debug(f"Pause {self.pause} seconds")
        await asyncio.sleep(self.pause)
        for index, _ in enumerate(range(self.max_tries), start=1):
            response_token: dict = await self._send_request(params=dict(url=url))
            self.logger.debug(f"Try №{index}/{self.max_tries}: {response_token}")
            status: int = response_token.get('status')
            token: str = response_token.get('request')
            if status and token:
                return token
            self.logger.debug(f"Next try after {self.pause} seconds")
            await asyncio.sleep(self.pause)
        else:
            raise CaptchaTimeoutError

    async def _get_captcha_token(self, captcha_sitekey: str) -> str:
        self.logger.debug("Getting captcha...")
        self.logger.debug(f"Captcha_sitekey: {captcha_sitekey}")
        captcha_result: str = await self.__get_captcha_token(captcha_sitekey)
        self.logger.debug(f'Ответ от капчи пришел:\n{captcha_result}')
        self.logger.success("Getting captcha...OK")

        return captcha_result

    def __get_xsuperproperties(self) -> str:
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
        return str(xsuperproperties)
