import asyncio
import json
import ssl
import time
from abc import abstractmethod, ABC
from json import JSONDecodeError
from typing import Union, List

import aiohttp
import aiohttp.client_exceptions
import aiohttp.http_exceptions

from classes.db_interface import DBI
from config import logger, DISCORD_BASE_URL, PROXY_USER, PROXY_PASSWORD, DEFAULT_PROXY
from classes.token_datastorage import TokenDataStore


class RequestSender(ABC):
    _EXCEPTIONS: tuple = (
        asyncio.exceptions.TimeoutError,
        aiohttp.client_exceptions.ServerDisconnectedError,
        aiohttp.client_exceptions.ClientProxyConnectionError,
        aiohttp.client_exceptions.ClientHttpProxyError,
        aiohttp.client_exceptions.ClientOSError,
        aiohttp.client_exceptions.TooManyRedirects,
    )

    def __init__(self):
        self.proxy: str = ''
        self.token: str = ''
        self.url: str = ''

    @abstractmethod
    async def _send(self) -> dict:
        self.proxy_data: str = f"http://{PROXY_USER}:{PROXY_PASSWORD}@{self.proxy}/"
        answer: dict = {
            "status": 0,
            "data": ''
        }
        return answer


class GetRequest(RequestSender):

    @logger.catch
    async def _send(self) -> dict:
        answer: dict = await super()._send()

        async with aiohttp.ClientSession() as session:
            print(f"URL: {self.url}")
            params: dict = {
                'url': self.url,
                "proxy": self.proxy_data,
                "ssl": False,
                "timeout": 10
            }
            if self.token:
                session.headers['authorization']: str = self.token
            try:
                async with session.get(**params) as response:
                    answer.update(
                        status=response.status,
                        data=await response.text()
                    )
            except self._EXCEPTIONS as err:
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


class GetMe(GetRequest):

    async def get_discord_id(self, token: str, proxy: str) -> str:
        self.proxy = proxy
        self.token = token
        self.url: str = f'https://discord.com/api/v9/users/@me'
        answer: dict = await self._send()
        if answer.get("status"):
            return json.loads(answer["data"])["id"]
        return ''


class ProxyChecker(GetRequest):

    def __init__(self):
        super().__init__()
        self.url: str = 'https://www.google.com'

    @logger.catch
    async def _check_proxy(self, proxy: str) -> int:
        """Отправляет запрос через прокси, возвращает статус код ответа"""

        self.proxy: str = proxy
        answer: dict = await self._send()

        return answer.get("status")

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
    async def check_proxy(self, proxy: str):

        answer: int = await self._check_proxy(proxy=proxy)
        if answer == 200:
            return proxy
        return await self.get_checked_proxy()


class GetChannelData(GetRequest):
    def __init__(self):
        super().__init__()
        self.limit: int = 1
        self.channel: Union[str, int] = 0

    async def _send(self) -> dict:
        self.url: str = DISCORD_BASE_URL + f'{self.channel}/messages?limit={self.limit}'
        return await super()._send()


class TokenChecker(GetChannelData):

    @logger.catch
    async def _check_token(self, proxy: str, token, channel: Union[str, int]) -> int:
        """Отправляет запрос через прокси, возвращает статус код ответа"""

        self.proxy: str = proxy
        self.token: str = token
        self.channel: int = channel
        answer: dict = await self._send()

        return answer.get("status")

    @logger.catch
    async def check_token(self, proxy: str, token: str, channel: int) -> dict:
        """Returns valid token else 'bad token'"""

        answer: dict = {
            "success": False,
            "message": '',
        }
        status: int = await self._check_token(proxy=proxy, token=token, channel=channel)
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


class PostRequest(RequestSender):

    def __init__(self):
        super().__init__()
        self.data_for_send: dict = {}

    @logger.catch
    async def _send(self) -> dict:
        """Отправляет данные в дискорд канал"""

        answer: dict = await super()._send()
        async with aiohttp.ClientSession() as session:
            params: dict = {
                'url': self.url,
                "proxy": self.proxy_data,
                "ssl": False,
                "timeout": 10,
                "json": self.data_for_send
            }
            if self.token:
                session.headers['authorization']: str = self.token
            try:
                async with session.post(**params) as response:
                    answer.update(
                        status=response.status,
                        data=await response.text()
                    )
            except self._EXCEPTIONS as err:
                logger.info(f"Token check Error: {err}")
            except aiohttp.http_exceptions.BadHttpMessage as err:
                logger.error("МУДАК ПРОВЕРЬ ПОРТ ПРОКСИ!!!", err)
                if "Proxy Authentication Required" in err:
                    answer.update(status=407)
            except (ssl.SSLError, OSError) as err:
                logger.error("Ошибка авторизации прокси:", err)
                if "Proxy Authentication Required" in err:
                    answer.update(status=407)
                # TODO
        #         if status_code == 407:
        #             new_proxy: str = await SomeChecker().get_checked_proxy(self.__datastore.telegram_id)
        #             if new_proxy == 'no proxies':
        #                 return
        #             self.__datastore.proxy = new_proxy
        #             await self.__send_data()
        return answer


class SendMessageToChannel(PostRequest):

    def __init__(self, datastore: 'TokenDataStore'):
        super().__init__()
        self._datastore: 'TokenDataStore' = datastore

    @logger.catch
    async def typing(self) -> None:
        """Имитирует "Пользователь печатает" в чате дискорда."""

        logger.debug("Typing...")

        self.url = f'https://discord.com/api/v9/channels/{self._datastore.channel}/typing'
        answer: dict = await self._send()
        if answer.get("status") != 204:
            logger.warning(f"Typing: {answer}")
        await asyncio.sleep(2)

    async def send_data(self) -> dict:
        """
        Sends data to discord channel
        :param datastore:
        :return:
        """

        self.token = self._datastore.token
        self.proxy = self._datastore.proxy
        self.data_for_send = self._datastore.data_for_send

        await self.typing()
        await self.typing()
        self.url = DISCORD_BASE_URL + f'{self._datastore.channel}/messages?'

        return await self._send()


async def tests():
    print(await GetMe().get_discord_id(token=token, proxy=DEFAULT_PROXY))
    print(await ProxyChecker().check_proxy(DEFAULT_PROXY))
    print(await TokenChecker().check_token(token=token, proxy=DEFAULT_PROXY, channel=channel))
    print(await SendMessageToChannel(datastore=datastore).send_data())


if __name__ == '__main__':
    token = "OTMzMTE5MDEzNzc1NjI2MzAy.YlcTyQ.AdyEjeWdZ_GL7xvMhitpSKV_qIk"
    telegram_id = "305353027"
    channel = 932256559394861079
    text = "done?"
    datastore = TokenDataStore(telegram_id=telegram_id)
    datastore.token = token
    datastore.proxy = DEFAULT_PROXY
    datastore.channel = str(channel)
    datastore.data_for_send = {
        "content": text,
        "tts": "false",
    }
    try:
        asyncio.new_event_loop().run_until_complete(tests())
    except KeyboardInterrupt:
        pass
