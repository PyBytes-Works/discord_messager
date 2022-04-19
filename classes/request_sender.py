import asyncio
import ssl
from json import JSONDecodeError
from typing import List, Optional

import aiohttp
import aiohttp.client_exceptions
import aiohttp.http_exceptions

from config import logger, DISCORD_BASE_URL, PROXY_USER, PROXY_PASSWORD


class RequestSender:

    __EXCEPTIONS: tuple = (
        asyncio.exceptions.TimeoutError,
        aiohttp.client_exceptions.ServerDisconnectedError,
        aiohttp.client_exceptions.ClientProxyConnectionError,
        aiohttp.client_exceptions.ClientHttpProxyError,
        aiohttp.client_exceptions.ClientOSError,
        aiohttp.client_exceptions.TooManyRedirects,
    )

    def __init__(self, proxy: str = '', token: str = '', channel: int = 0, datastore=None):
        self.limit: int = 1
        self.proxy: str = proxy
        self.token: str = token
        self.channel: int = channel
        self.__datastore = datastore
        if datastore is not None:
            self.limit: int = 100
            self.proxy: str = datastore.proxy
            self.token: str = datastore.token
            self.channel: int = datastore.channel
        self.proxy_data: str = f"http://{PROXY_USER}:{PROXY_PASSWORD}@{self.proxy}/"
        self.url: str = DISCORD_BASE_URL + f'{self.channel}/messages?limit={self.limit}'

    @logger.catch
    async def check_proxy(self) -> int:
        """Отправляет запрос через прокси, возвращает статус код ответа"""

        async with aiohttp.ClientSession() as session:
            url: str = "https://www.google.com"
            if self.token:
                session.headers['authorization']: str = self.token
                url: str = self.url
            try:
                async with session.get(
                        url=url, proxy=self.proxy_data, ssl=False, timeout=10
                ) as response:
                    return response.status
            except self.__EXCEPTIONS as err:
                logger.info(f"Token check Error: {err}")
            except aiohttp.http_exceptions.BadHttpMessage as err:
                logger.error("МУДАК ПРОВЕРЬ ПОРТ ПРОКСИ!!!", err)
                if "Proxy Authentication Required" in err:
                    return 407
            except (ssl.SSLError, OSError) as err:
                logger.error("Ошибка авторизации прокси:", err)
                if "Proxy Authentication Required" in err:
                    return 407
        return 0

    @logger.catch
    async def get_data_from_channel(self) -> 'aiohttp.ClientResponse':
        """Отправляет запрос к АПИ"""

        async with aiohttp.ClientSession() as session:
            session.headers['authorization']: str = self.token
            try:
                async with session.get(url=self.url, proxy=self.proxy_data, ssl=False, timeout=10) as response:
                    status_code = response.status
                    if status_code == 200:
                        return response
                    else:
                        logger.error(f"F: __get_data_from_api_aiohttp error: {status_code}: {await response.text()}")
            except self.__EXCEPTIONS as err:
                logger.error(f"F: __get_data_from_api_aiohttp error: {err}", err)
            except aiohttp.http_exceptions.BadHttpMessage as err:
                logger.error("МУДАК ПРОВЕРЬ ПОРТ ПРОКСИ!!!", err)
            except JSONDecodeError as err:
                logger.error("F: __send_data_to_api: JSON ERROR:", err)
