import asyncio
import json
import ssl
from abc import abstractmethod, ABC
from typing import Union

import aiohttp
import aiohttp.client_exceptions
import aiohttp.http_exceptions

from classes.db_interface import DBI
from classes.errors_sender import ErrorsSender
from config import logger, DISCORD_BASE_URL, PROXY_USER, PROXY_PASSWORD
from classes.token_datastorage import TokenData


class RequestSender(ABC):

    def __init__(self):
        self.proxy: str = ''
        self.token: str = ''
        self.url: str = ''
        self._EXCEPTIONS: tuple = (
            asyncio.exceptions.TimeoutError,
            aiohttp.client_exceptions.ServerDisconnectedError,
            aiohttp.client_exceptions.ClientProxyConnectionError,
            aiohttp.client_exceptions.ClientHttpProxyError,
            aiohttp.client_exceptions.ClientOSError,
            aiohttp.client_exceptions.TooManyRedirects,
        )
        self._params: dict = {}
        self._error_params: dict = {
            "proxy": self.proxy if self.proxy else 'no proxy',
            "token": self.token if self.token else 'no token',
        }

    @abstractmethod
    async def _send(self, *args, **kwargs) -> dict:
        pass

    async def _send_request(self) -> dict:
        self.proxy_data: str = f"http://{PROXY_USER}:{PROXY_PASSWORD}@{self.proxy}/"
        answer: dict = {
            "status": 0,
            "answer_data": ''
        }
        self._params: dict = {
            'url': self.url,
            "proxy": self.proxy_data,
            "ssl": False,
            "timeout": 10
        }
        try:
            answer: dict = await self._send()
        except aiohttp.client_exceptions.ClientHttpProxyError as err:
            logger.error(f"aiohttp.client_exceptions.ClientHttpProxyError: 407 {err}")
            answer.update(status=407)
        # except Exception as err:
        #     logger.error(f"Exception raised {err}")

        return answer


class GetRequest(RequestSender):

    async def _send(self) -> dict:
        async with aiohttp.ClientSession() as session:
            if self.token:
                session.headers['authorization']: str = self.token
            async with session.get(**self._params) as response:
                return {
                    "status": response.status,
                    "answer_data": await response.text()
                }

        # answer: dict = await super()._send()

        # async with aiohttp.ClientSession() as session:
        #
        #     params: dict = {
        #         'url': self.url,
        #         "proxy": self.proxy_data,
        #         "ssl": False,
        #         "timeout": 10
        #     }
        #     # TODO разделить на пост и гет запросы
        #     if self.token:
        #         session.headers['authorization']: str = self.token
        #     try:
        #         async with session.get(**params) as response:
        #             answer.update(
        #                 status=response.status,
        #                 data=await response.text()
        #             )
        #     except aiohttp.client_exceptions.ClientConnectorError as err:
        #         logger.error(f"GetRequest: Proxy check Error: {err}"
        #                      f"\nProxy: {self.proxy}")
        #         await ErrorsSender.proxy_not_found_error()
        #         answer.update(status=407)
        #     except aiohttp.http_exceptions.BadHttpMessage as err:
        #         logger.error(f"GetRequest: МУДАК ПРОВЕРЬ ПОРТ ПРОКСИ!!! {err}"
        #                      f"\nProxy: {self.proxy}")
        #         if "Proxy Authentication Required" in err:
        #             answer.update(status=407)
        #     except (ssl.SSLError, OSError) as err:
        #         logger.error(f"GetRequest: Ошибка авторизации прокси: {err}"
        #                      f"\nProxy: {self.proxy}")
        #         if "Proxy Authentication Required" in err:
        #             answer.update(status=407)
        #     except self._EXCEPTIONS as err:
        #         logger.error(f"GetRequest: _EXCEPTIONS: {err}")
        #
        # return answer


class GetMe(GetRequest):

    async def get_discord_id(self, token: str, proxy: str) -> str:
        self.proxy = proxy
        self.token = token
        self.url: str = f'https://discord.com/api/v9/users/@me'
        answer: dict = await self._send_request()
        self._error_params.update(answer=answer)
        answer: dict = await ErrorsSender(**self._error_params).handle_errors()
        return answer.get("answer_data", {}).get("id", '')


class ChannelData(GetRequest):

    def __init__(self, datastore: 'TokenData'):
        super().__init__()
        self._datastore: 'TokenData' = datastore
        self.limit: int = 100

    async def _send(self) -> dict:
        self.url: str = DISCORD_BASE_URL + f'{self._datastore.channel}/messages?limit={self.limit}'
        return await super()._send()


class ProxyChecker(GetRequest):

    def __init__(self):
        super().__init__()
        self.url: str = 'https://www.google.com'

    @logger.catch
    async def _check_proxy(self, proxy: str) -> int:
        """Отправляет запрос через прокси, возвращает статус код ответа"""

        self.proxy: str = proxy

        answer: dict = await self._send_request()
        return answer.get("status")

    @logger.catch
    async def get_checked_proxy(self, telegram_id: str) -> str:
        """Возвращает рабочую прокси из базы данных, если нет рабочих возвращает 'no proxies'"""

        result: str = 'no proxies'
        if not await DBI.get_proxy_count():
            return result
        proxy: str = str(await DBI.get_user_proxy(telegram_id=telegram_id))
        if await self._check_proxy(proxy=proxy) == 200:
            logger.error(f"Proxy {proxy} doesn`t work. Will be delete.")
            return proxy
        if not await DBI.update_proxies_for_owners(proxy=proxy):
            return result
        return await self.get_checked_proxy(telegram_id=telegram_id)


class TokenChecker(GetRequest):

    def __init__(self):
        super().__init__()
        self.limit: int = 1
        self.channel: Union[str, int] = 0

    @logger.catch
    async def check_token(self, proxy: str, token: str, channel: int, telegram_id: str) -> bool:
        """Returns valid token else 'bad token'"""

        self.proxy: str = proxy
        self.token: str = token
        self.channel: int = channel
        self.url: str = DISCORD_BASE_URL + f'{self.channel}/messages?limit={self.limit}'

        answer: dict = await self._send_request()
        status: int = answer.get("status")
        if status == 200:
            return True

        self._error_params.update(answer=answer, telegram_id=telegram_id)
        await ErrorsSender(**self._error_params).handle_errors()


class PostRequest(RequestSender):

    def __init__(self):
        super().__init__()
        self._data_for_send: dict = {}

    async def _send(self) -> dict:
        """Отправляет данные в дискорд канал"""
        async with aiohttp.ClientSession() as session:
            if self.token:
                session.headers['authorization']: str = self.token
            self._params.update(json=self._data_for_send)
            async with session.post(**self._params) as response:
                return {
                    "status": response.status,
                    "answer_data": await response.text()
            }

        #
        # answer: dict = await super()._send()
        # async with aiohttp.ClientSession() as session:
        #     params: dict = {
        #         'url': self.url,
        #         "proxy": self.proxy_data,
        #         "ssl": False,
        #         "timeout": 10,
        #         "json": self._data_for_send
        #     }
        #     if self.token:
        #         session.headers['authorization']: str = self.token
        #     try:
        #         async with session.post(**params) as response:
        #             answer.update(
        #                 status=response.status,
        #                 data=await response.text()
        #             )
        #     except aiohttp.client_exceptions.ClientConnectorError as err:
        #         logger.error(f"GetRequest: Proxy check Error: {err}")
        #         await ErrorsSender.proxy_not_found_error()
        #         answer.update(status=407)
        #     except aiohttp.http_exceptions.BadHttpMessage as err:
        #         logger.error("GetRequest: МУДАК ПРОВЕРЬ ПОРТ ПРОКСИ!!!", err)
        #         if "Proxy Authentication Required" in err:
        #             answer.update(status=407)
        #     except (ssl.SSLError, OSError) as err:
        #         logger.error("GetRequest: Ошибка авторизации прокси:", err)
        #         if "Proxy Authentication Required" in err:
        #             answer.update(status=407)
        #     except self._EXCEPTIONS as err:
        #         logger.error("GetRequest: _EXCEPTIONS: ", err)
        #
        # return answer
