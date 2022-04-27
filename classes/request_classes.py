import asyncio
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
            aiohttp.client_exceptions.ClientOSError,
            aiohttp.client_exceptions.TooManyRedirects,
        )
        self._params: dict = {}
        self._error_params: dict = {}

    @abstractmethod
    async def _send(self, *args, **kwargs) -> dict:
        pass

    def _update_err_params(self, answer: dict, telegram_id: str = ''):
        self._error_params: dict = {
            "proxy": self.proxy if self.proxy else '',
            "token": self.token if self.token else '',
            "answer": answer,
            "telegram_id": telegram_id if telegram_id else ''
        }

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
            "timeout": 10,
            "trust_env": True
        }
        try:
            # logger.debug(self._params)
            answer: dict = await self._send()
        except (
                aiohttp.client_exceptions.ClientHttpProxyError,
                aiohttp.client_exceptions.ClientConnectorError,
                aiohttp.http_exceptions.BadHttpMessage
        ) as err:
            logger.error(f"PROXY ERROR: 407 {err}")
            answer.update(status=407)
        except self._EXCEPTIONS as err:
            logger.error(f"GetRequest: _EXCEPTIONS: {err}")
            answer.update(status=-100)

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


class GetMe(GetRequest):

    async def get_discord_id(self, token: str, proxy: str) -> str:
        self.proxy = proxy
        self.token = token
        self.url: str = f'https://discord.com/api/v9/users/@me'
        answer: dict = await self._send_request()
        self._update_err_params(answer=answer)
        # logger.debug("GetMe.get_discord_id call error handling:"
        #              f"\nParams: {self._error_params}")
        answer: dict = await ErrorsSender(**self._error_params).handle_errors()
        return answer.get("answer_data", {}).get("id", '')


class ChannelData(GetRequest):

    def __init__(self, datastore: 'TokenData'):
        super().__init__()
        self._datastore: 'TokenData' = datastore
        self.limit: int = 100
        self.url: str = DISCORD_BASE_URL + f'{self._datastore.channel}/messages?limit={self.limit}'


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
            return proxy
        logger.error(f"Proxy {proxy} doesn`t work. Will be delete.")
        if not await DBI.update_proxies_for_owners(proxy=proxy):
            return result
        return await self.get_checked_proxy(telegram_id=telegram_id)


class TokenChecker(GetRequest):

    def __init__(self):
        super().__init__()
        self.channel: Union[str, int] = 0

    @logger.catch
    async def check_token(self, proxy: str, token: str, channel: int, telegram_id: str) -> bool:
        """Returns valid token else 'bad token'"""

        self.proxy: str = proxy
        self.token: str = token
        self.channel: int = channel
        self.url: str = DISCORD_BASE_URL + f'{self.channel}/messages?limit=1'

        answer: dict = await self._send_request()
        status: int = answer.get("status")
        if status == 200:
            return True
        self._update_err_params(answer=answer, telegram_id=telegram_id)
        # logger.debug("TokenChecker.check_token call error handling:"
        #              f"\nParams: {self._error_params}")
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
