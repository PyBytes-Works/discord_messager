import asyncio
import json
import ssl
from json import JSONDecodeError
from typing import Union, List

import aiohttp
import aiohttp.client_exceptions
import aiohttp.http_exceptions

from classes.db_interface import DBI
from config import logger, DISCORD_BASE_URL, PROXY_USER, PROXY_PASSWORD
from classes.token_datastorage import TokenDataStore


class RequestSender:

    __EXCEPTIONS: tuple = (
        asyncio.exceptions.TimeoutError,
        aiohttp.client_exceptions.ServerDisconnectedError,
        aiohttp.client_exceptions.ClientProxyConnectionError,
        aiohttp.client_exceptions.ClientHttpProxyError,
        aiohttp.client_exceptions.ClientOSError,
        aiohttp.client_exceptions.TooManyRedirects,
    )

    def __init__(self):
        self.limit: int = 1
        self.proxy: str = ''
        self.token: str = ''
        self.channel: Union[str, int] = 0

    @logger.catch
    async def get_request(self, datastore: 'TokenDataStore') -> List[dict]:
        """Отправляет GET запрос к АПИ"""

        self.proxy: str = datastore.proxy
        self.token: str = datastore.token
        self.channel: Union[str, int] = datastore.channel

        answer: dict = await self._send_get_request()
        status: int = answer.get("status")
        if not status:
            logger.error(f"get_data_from_channel error: ")
        elif status == 200:
            try:
                return json.loads(answer.get("data"))
            except JSONDecodeError as err:
                logger.error("F: get_data_from_channel: JSON ERROR:", err)

    @logger.catch
    async def post_request(self, datastore: 'TokenDataStore', data: dict):
        """Отправляет POST запрос к АПИ"""
        # TODO Написать из сендера
        pass

    @logger.catch
    async def get_checked_proxy(self, telegram_id: str) -> str:
        """Возвращает рабочую прокси из базы данных, если нет рабочих возвращает 'no proxies'"""

        if not await DBI.get_proxy_count():
            return 'no proxies'
        proxy: str = str(await DBI.get_user_proxy(telegram_id=telegram_id))
        if await self._check_proxy(proxy=proxy) == 200:
            return proxy
        if not await DBI.update_proxies_for_owners(proxy=proxy):
            return 'no proxies'

        return await self.get_checked_proxy(telegram_id=telegram_id)

    @logger.catch
    async def check_token(self, proxy: str, token: str, channel: int) -> dict:
        """Returns valid token else 'bad token'"""

        answer: dict = {
            "success": False,
            "message": '',
        }
        status: int = await self._check_proxy(proxy=proxy, token=token, channel=channel)
        if status == 200:
            answer.update({
                "success": True,
                "proxy": proxy,
                "token": token,
                "channel": channel
            })
        elif status == 407:
            answer.update(message='bad proxy')
        else:
            answer.update(message='bad token')

        return answer

    @logger.catch
    async def get_me(self, token: str):
        # TODO написать
        pass

    @logger.catch
    async def check_proxy(self, proxy: str):

        self.proxy = proxy
        answer: dict = await self._send_get_request()
        if answer.get("status") == 200:
            return proxy
        return await self.get_checked_proxy()

    @logger.catch
    async def _check_proxy(self, proxy: str, token: str = '', channel: Union[str, int] = 0) -> int:
        """Отправляет запрос через прокси, возвращает статус код ответа"""

        # TODO отрефакторить метод, у него двойной функционал
        self.proxy: str = proxy
        self.token: str = token
        self.channel: int = channel
        answer: dict = await self._send_get_request()

        return answer.get("status")

    @logger.catch
    async def _send_get_request(self) -> dict:

        self.proxy_data: str = f"http://{PROXY_USER}:{PROXY_PASSWORD}@{self.proxy}/"
        self.url: str = DISCORD_BASE_URL + f'{self.channel}/messages?limit={self.limit}'

        answer: dict = {
            "status": 0,
            "data": ''
        }
        async with aiohttp.ClientSession() as session:
            params: dict = {
                'url': "https://www.google.com",
                "proxy": self.proxy_data,
                "ssl": False,
                "timeout": 10
            }
            if self.token:
                session.headers['authorization']: str = self.token
                params.update(url=self.url)
            try:
                async with session.get(**params) as response:
                    answer.update(
                        status=response.status,
                        data=await response.text()
                    )
            except self.__EXCEPTIONS as err:
                logger.info(f"Token check Error: {err}")
            except aiohttp.http_exceptions.BadHttpMessage as err:
                logger.error("МУДАК ПРОВЕРЬ ПОРТ ПРОКСИ!!!", err)
                if "Proxy Authentication Required" in err:
                    answer.update(status=407)
            except (ssl.SSLError, OSError) as err:
                logger.error("Ошибка авторизации прокси:", err)
                if "Proxy Authentication Required" in err:
                    answer.update(status=407)

        return answer
