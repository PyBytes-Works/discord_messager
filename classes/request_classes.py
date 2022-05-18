import asyncio
from abc import abstractmethod, ABC
from typing import Union, Optional

import aiohttp
import aiohttp.client_exceptions
import aiohttp.http_exceptions

from classes.db_interface import DBI
from classes.errors_reporter import ErrorsReporter
from config import logger, DISCORD_BASE_URL, PROXY_USER, PROXY_PASSWORD
from classes.token_datastorage import TokenData


class RequestSender(ABC):

    def __init__(self, url: str = ''):
        self.proxy: str = ''
        self.token: str = ''
        self.url: str = url
        self.telegram_id: str = ''
        self._params: dict = {}
        self._error_params: dict = {}
        self.datastore: Optional['TokenData'] = None
        self.trust_env: bool = False
        self.timeout: int = 30

    @abstractmethod
    async def _send(self, *args, **kwargs) -> dict:
        pass

    def _update_error_params(self, answer: dict):
        self._error_params.update(
            {
                "answer": answer,
                "proxy": self.proxy if self.proxy else '',
                "token": self.token if self.token else '',
                "telegram_id": self.telegram_id if self.telegram_id else '',
            }
        )
        if self.datastore:
            self._error_params.update(
                {
                    "datastore": self.datastore,
                    "proxy": self.datastore.proxy,
                    "token": self.datastore.token,
                    "telegram_id": self.datastore.telegram_id,
                }
            )

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
            "timeout": self.timeout,
        }

        text: str = ''
        try:
            user_id: int = 112176570
            # TODO для пользователя с ид 112176570 отправлять запросы не через прокси.
            if int(self.datastore.telegram_id) == user_id:
                logger.warning(f"\n\tSending request without proxy for user {user_id}:")
                self._params: dict = {
                    'url': self.url,
                    "ssl": False,
                    "timeout": self.timeout,
                }
            await asyncio.sleep(2)
            answer: dict = await self._send()
        except asyncio.exceptions.TimeoutError as err:
            logger.error(f"asyncio.exceptions.TimeoutError: {err}")
            answer.update(status=-99)
        except aiohttp.http_exceptions.BadHttpMessage as err:
            logger.error(f"aiohttp.http_exceptions.BadHttpMessage: {err}")
            answer.update(status=407)
        except aiohttp.client_exceptions.ClientHttpProxyError as err:
            logger.error(f"aiohttp.client_exceptions.ClientHttpProxyError: {err}")
            answer.update(status=407)
        except aiohttp.client_exceptions.ClientConnectorError as err:
            logger.error(f"aiohttp.client_exceptions.ClientConnectorError: {err}")
            answer.update(status=407)
        except aiohttp.client_exceptions.ServerDisconnectedError as err:
            logger.error(f"aiohttp.client_exceptions.ServerDisconnectedError: {err}")
        except aiohttp.client_exceptions.ClientOSError as err:
            logger.error(f"aiohttp.client_exceptions.ClientOSError: {err}")
            answer.update(status=-98)
        except aiohttp.client_exceptions.TooManyRedirects as err:
            text = f"aiohttp.client_exceptions.TooManyRedirects: {err}"
        except Exception as err:
            text = f"Exception: {err}"

        if text:
            logger.error(f"\n{self._send_request.__qualname__}: {text}")
            answer.update(status=-100)
        status = answer.get("status")
        if status not in range(200, 205):
            error_text: str = (
                f"\n{self._send_request.__qualname__}:"
                f"\nStatus: {status}"
                f"\nUrl: {self.url}"
                f"\nProxy: {self.proxy}")
            if self.token:
                error_text += f"\nToken: {self.token}"
            logger.error(error_text)

        self._update_error_params(answer=answer)
        answer: dict = await ErrorsReporter(**self._error_params).handle_errors()

        return answer


class GetRequest(RequestSender):
    """Класс для отправки GET запросов"""

    def __init__(self):
        super().__init__()

    async def _send(self) -> dict:
        conn = aiohttp.TCPConnector(verify_ssl=False)
        async with aiohttp.ClientSession(trust_env=self.trust_env, connector=conn) as session:
            if self.token:
                session.headers['authorization']: str = self.token
            async with session.get(**self._params) as response:
                return {
                    "status": response.status,
                    "answer_data": await response.text()
                }


class PostRequest(RequestSender):
    """Класс для отправки POST запросов"""

    def __init__(self):
        super().__init__()
        self._data_for_send: dict = {}

    async def _send(self) -> dict:
        """Отправляет данные в дискорд канал"""

        conn = aiohttp.TCPConnector(verify_ssl=False)
        async with aiohttp.ClientSession(trust_env=self.trust_env, connector=conn) as session:
            if self.token:
                session.headers['authorization']: str = self.token
            self._params.update(json=self._data_for_send)
            async with session.post(**self._params) as response:
                return {
                    "status": response.status,
                    "answer_data": await response.text()
                }


class GetMe(GetRequest):
    """Класс для получения дискорд_ид по токену"""

    async def get_discord_id(self, token: str, proxy: str) -> str:
        self.proxy = proxy
        self.token = token
        self.url: str = f'https://discord.com/api/v9/users/@me'
        answer: dict = await self._send_request()

        return answer.get("answer_data", {}).get("id", '')


class ChannelData(GetRequest):
    """Класс для получения сообщений из канала дискорда"""

    def __init__(self, datastore: 'TokenData'):
        super().__init__()
        self.datastore: 'TokenData' = datastore
        self.limit: int = 100
        self.url: str = DISCORD_BASE_URL + f'{self.datastore.channel}/messages?limit={self.limit}'


class ProxyChecker(GetRequest):
    """Класс для проверки прокси"""

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
    """Класс для проверки токена в дискорд канале"""

    def __init__(self):
        super().__init__()
        self.channel: Union[str, int] = 0

    @logger.catch
    async def check_token(self, proxy: str, token: str, channel: int, telegram_id: str) -> bool:
        """Returns valid token else 'bad token'"""

        self.proxy: str = proxy
        self.token: str = token
        self.channel: int = channel
        self.telegram_id = telegram_id
        self.url: str = DISCORD_BASE_URL + f'{self.channel}/messages?limit=1'

        answer: dict = await self._send_request()

        return answer.get("status") == 200
