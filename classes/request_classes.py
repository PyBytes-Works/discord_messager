import asyncio
from abc import abstractmethod, ABC
from typing import Union, Optional

import aiohttp.client_exceptions
import aiohttp.http_exceptions

from classes.db_interface import DBI
from classes.errors_reporter import ErrorsReporter
from config import logger, DISCORD_BASE_URL, settings
from classes.token_datastorage import TokenData


class RequestSender(ABC):
    """
    ABC class for requests

    Attributes

        proxy: str = ''

        token: str = ''

        url: str = url

        telegram_id: str = ''

        datastore: Optional['TokenData'] = None

        trust_env: bool = False

        timeout: int = 30

        request_delay: int = 3

    Methods

        _send_request
    """

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
        self.request_delay: int = 3

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

        answer: dict = {
            "status": 0,
            "answer_data": ''
        }
        self._params: dict = {
            'url': self.url,
            "ssl": False,
            "timeout": self.timeout,
        }
        if self.proxy:
            self.proxy_data: str = f"http://{settings.PROXY_USER}:{settings.PROXY_PASSWORD}@{self.proxy}/"
            self._params.update(proxy=self.proxy_data)
        session_params: dict = {
            "trust_env": True,
            "connector": aiohttp.TCPConnector(),
        }
        if self.token:
            session_params.update({
                'headers': {
                    'authorization': self.token
                }
            })
        try:
            async with aiohttp.ClientSession(**session_params) as session:
                answer: dict = await self._send(session)
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
            answer.update(status=-96)
        except aiohttp.client_exceptions.TooManyRedirects as err:
            logger.error(f"aiohttp.client_exceptions.TooManyRedirects: {err}")
            answer.update(status=-97)
        except aiohttp.client_exceptions.ClientOSError as err:
            logger.error(f"aiohttp.client_exceptions.ClientOSError: {err}")
            answer.update(status=-98)
        except asyncio.exceptions.TimeoutError as err:
            logger.error(f"asyncio.exceptions.TimeoutError: {err}")
            answer.update(status=-99)
        except Exception as err:
            logger.error(f"Exception: {err}")
            answer.update(status=-100)

        status = answer.get("status")
        if status not in range(200, 205):
            error_text: str = (
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

    async def _send(self, session) -> dict:
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

    async def _send(self, session) -> dict:
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
        self.url: str = "https://ifconfig.me/all.json"

    @logger.catch
    async def _check_proxy(self, proxy: str) -> int:
        """Отправляет запрос через прокси, возвращает статус код ответа"""

        self.proxy: str = proxy
        answer: dict = await self._send_request()
        return answer.get("status")

    @logger.catch
    async def get_checked_proxy(self, telegram_id: str) -> str:
        """Возвращает рабочую прокси из базы данных, если нет рабочих возвращает 'no proxies'"""

        if not await DBI.get_proxy_count():
            return 'no proxies'
        proxy: str = str(await DBI.get_user_proxy(telegram_id=telegram_id))
        if await self._check_proxy(proxy=proxy) == 200:
            return proxy
        logger.error(f"Proxy {proxy} doesn`t work. Will be delete.")
        if not await DBI.update_proxies_for_owners(proxy=proxy):
            return 'no proxies'
        return await self.get_checked_proxy(telegram_id=telegram_id)

    @logger.catch
    async def update_tested_proxies(self) -> dict[str: int]:
        """Проверяет все прокси в БД, возвращает словарь со статусами"""

        logger.info("Proxies check begin...")
        self.timeout = 5
        db_proxies: list[str] = await DBI.get_all_proxies()
        proxies = db_proxies[:]
        proxies.extend(settings.PROXIES)
        result = {}
        for proxy in set(proxies):
            logger.debug(f"Checking proxy: {proxy} ...")
            self.proxy = proxy
            answer: dict = await self._send_request()
            status: int = answer.get("status")
            if status != 200:
                logger.warning(f"Checking proxy: {proxy}: FAIL")
                # await DBI.delete_proxy(proxy)
                logger.warning("Proxy should deleted from DB.")
                continue
            answer_data = answer.get("answer_data", {})
            ip_addr: str = answer_data.get("ip_addr", '')
            if ip_addr == proxy.split(':')[0]:
                result.update({
                    proxy: status
                })
                if proxy not in db_proxies:
                    await DBI.add_new_proxy(proxy)
                    logger.info("Proxy added to DB.")
                logger.debug(f"Checking proxy: {proxy}: OK")

        await DBI.delete_proxy_for_all_users()
        await DBI.set_new_proxy_for_all_users()

        return result


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
