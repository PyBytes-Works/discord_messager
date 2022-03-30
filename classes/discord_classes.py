import datetime
import os
import random
import ssl
from json import JSONDecodeError
from typing import List, Tuple, Optional

import asyncio
import aiohttp
import requests
import aiohttp.client_exceptions
import aiohttp.http_exceptions
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove

from classes.vocabulary import Vocabulary
from config import logger
from utils import send_report_to_admins
from keyboards import cancel_keyboard, user_menu_keyboard
from utils import RedisInterface
from models import User, Token, Proxy


PROXY_USER = os.getenv("PROXY_USER")
PROXY_PASSWORD = os.getenv("PROXY_PASSWORD")


class MessageReceiver:

    __EXCEPTIONS: tuple = (
        asyncio.exceptions.TimeoutError,
        aiohttp.client_exceptions.ServerDisconnectedError,
        aiohttp.client_exceptions.ClientProxyConnectionError,
        aiohttp.client_exceptions.ClientHttpProxyError,
        aiohttp.client_exceptions.ClientOSError,
        aiohttp.client_exceptions.TooManyRedirects,
        ConnectionResetError
    )

    """Выбирает токен для отправки сообщения и вызывает метод вызова сообщения,
    проверяет его ответ, и, если есть свободные токены - повторяет процесс.
    При ошибке возвращает ее в телеграм"""

    @logger.catch
    def __init__(self, datastore: 'TokenDataStore'):
        self.__datastore: 'TokenDataStore' = datastore

    @classmethod
    async def _is_proxy_work(cls, proxy: str) -> bool:
        """Проверяет прокси на работоспособность"""

        if await cls._send_get_request(proxy=proxy) == 200:
            return True

    @classmethod
    async def get_proxy(cls, telegram_id: str) -> str:
        """Возвращает рабочую прокси из базы данных, если нет рабочих возвращает 'no proxies'"""

        if not Proxy.get_proxy_count():
            return 'no proxies'
        proxy: str = str(User.get_proxy(telegram_id=telegram_id))
        if await cls._is_proxy_work(proxy=proxy):
            return proxy
        if not Proxy.update_proxies_for_owners(proxy=proxy):
            return 'no proxies'

        return await cls.get_proxy(telegram_id=telegram_id)

    @classmethod
    async def check_user_data(cls, token: str, proxy: str, channel: int) -> dict:
        """Returns checked dictionary for user data

        Save valid data to instance variables """
        request_result: str = await cls.__check_token(token=token, proxy=proxy, channel=channel)
        result = {"token": request_result}
        if request_result != "bad token":
            result["channel"] = channel
        elif request_result == 'no proxies':
            return {"token": request_result}

        return result

    @logger.catch
    async def get_message(self) -> dict:
        """Получает данные из АПИ, выбирает случайное сообщение и возвращает ID сообщения
        и само сообщение"""

        result = {"work": False}
        token_data: dict = await self.__select_token_for_work()
        result_message: str = token_data.get("message")
        if result_message == "no pairs":
            result.update(token_data)
            return result

        token: str = token_data.get("token", '')
        if not token:
            result.update({"message": result_message})
            return result

        user_message, message_id = await self.__get_user_message_from_redis(token=token)

        filtered_data: dict = await self.__get_filtered_data()
        if filtered_data:
            replies: List[dict] = filtered_data.get("replies", [])
            if replies:
                result.update({"replies": replies})

        if message_id:
            self.__datastore.current_message_id = message_id
        elif filtered_data:
            self.__datastore.current_message_id = await self.__get_current_message_id(data=filtered_data)
        text_to_send: str = user_message if user_message else ''
        answer: dict = await MessageSender(datastore=self.__datastore).send_message(text=text_to_send)
        if not answer:
            logger.error("F: get_message ERROR: NO ANSWER ERROR")
            result.update({"message": "ERROR"})
            return result
        elif answer.get("status_code") != 200:
            result.update({"answer": answer, "token": token})
            return result

        self.__datastore.current_message_id = 0
        result.update({"work": True})

        timer: float = 7 + random.randint(0, 6)
        logger.info(f"Пауза между отправкой сообщений: {timer}")
        await asyncio.sleep(timer)

        return result

    @staticmethod
    @logger.catch
    async def __get_current_message_id(data: dict) -> int:
        message_id = 0
        filtered_messages: list = data.get("messages", [])
        if filtered_messages:
            result_data: dict = random.choice(filtered_messages)
            message_id = int(result_data.get("id"))

        return message_id

    @logger.catch
    async def __get_user_message_from_redis(self, token: str) -> Tuple[str, int]:
        """Возвращает данные из Редиса"""

        answer: str = ''
        message_id = 0
        redis_data: List[dict] = await RedisInterface(telegram_id=self.__datastore.telegram_id).load()
        if not redis_data:
            return answer, message_id
        for elem in redis_data:
            if not isinstance(elem, dict):
                continue
            answered = elem.get("answered", False)
            if not answered:
                if elem.get("token") == token:
                    answer = elem.get("answer_text", '')
                    if answer:
                        message_id = elem.get("message_id", 0)
                        elem.update({"answered": True})
                        await RedisInterface(telegram_id=self.__datastore.telegram_id).save(data=redis_data)
                        break

        return answer, message_id

    @logger.catch
    async def __select_token_for_work(self) -> dict:
        """
        Выбирает случайного токена дискорда из свободных, если нет свободных - пишет сообщение что
        свободных нет.
        """

        result: dict = {"message": "token ready"}
        all_tokens: List[dict] = Token.get_all_related_user_tokens(telegram_id=self.__datastore.telegram_id)
        if not all_tokens:
            result["message"] = "no pairs"
            return result
        current_time: int = int(datetime.datetime.now().timestamp())
        workers: list = [
            key
            for elem in all_tokens
            for key, value in elem.items()
            if current_time > value["time"] + value["cooldown"]
        ]
        if workers:
            random_token: str = random.choice(workers)
            result["token"]: str = random_token
            self.__datastore.create_datastore_data(random_token)
        else:
            min_token_data = {}
            for elem in all_tokens:
                min_token_data: dict = min(elem.items(), key=lambda x: x[1].get('time'))
            token: str = tuple(min_token_data)[0]
            self.__datastore.create_datastore_data(token)
            min_token_time: int = Token.get_time_by_token(token)
            delay: int = self.__datastore.cooldown - abs(min_token_time - current_time)
            self.__datastore.delay = delay
            text = "секунд"
            if delay > 60:
                minutes: int = delay // 60
                seconds: int = delay % 60
                if minutes < 10:
                    minutes: str = f"0{minutes}"
                if seconds < 10:
                    seconds: str = f'0{seconds}'
                delay: str = f"{minutes}:{seconds}"
                text = "минут"
            result["message"] = f"Все токены отработали. Следующий старт через {delay} {text}."

        return result

    @logger.catch
    async def __get_filtered_data(self) -> dict:
        """Отправляет запрос к АПИ"""

        result: dict = {}
        await asyncio.sleep(1 // 100)
        async with aiohttp.ClientSession() as session:
            session.headers['authorization']: str = self.__datastore.token
            limit: int = 100
            url: str = self.__datastore.get_channel_url() + f'{self.__datastore.channel}/messages?limit={limit}'
            proxy_data = f"http://{PROXY_USER}:{PROXY_PASSWORD}@{self.__datastore.proxy}/"
            try:
                async with session.get(url=url, proxy=proxy_data, ssl=False, timeout=10) as response:
                    status_code = response.status
                    if status_code == 200:
                        data: List[dict] = await response.json()
                    else:
                        logger.error(f"F: __get_data_from_api_aiohttp error: {status_code}: {response.text()}")
                        data: dict = {}
            except MessageReceiver.__EXCEPTIONS as err:
                logger.error(f"F: __get_data_from_api_aiohttp error: {err}", err)
            except aiohttp.http_exceptions.BadHttpMessage as err:
                logger.error("МУДАК ПРОВЕРЬ ПОРТ ПРОКСИ!!!", err)
            except JSONDecodeError as err:
                logger.error("F: __send_data_to_api: JSON ERROR:", err)
            else:
                # Дебагеррный файл, можно удалять
                # save_data_to_json(data=data)
                result: dict = await self.__data_filter(data=data)

        return result

    @logger.catch
    async def __data_filter(self, data: List[dict]) -> dict:
        """Фильтрует полученные данные"""

        messages = []
        replies = []
        result = {}
        summa = 0
        for elem in data:
            message: str = elem.get("content")
            message_time: 'datetime' = elem.get("timestamp")
            mes_time = datetime.datetime.fromisoformat(message_time).replace(tzinfo=None)
            delta = datetime.datetime.utcnow().replace(tzinfo=None) - mes_time
            if delta.seconds < self.__datastore.last_message_time:
                filtered_replies: dict = self.__replies_filter(elem=elem)
                if filtered_replies:
                    replies.append(filtered_replies)
                is_author_mate: bool = str(self.__datastore.mate_id) == str(elem["author"]["id"])
                my_message: bool = str(elem["author"]["id"]) == str(self.__datastore.my_discord_id)
                if is_author_mate and not my_message:
                    summa += len(message)
                    messages.append(
                        {
                            "id": elem.get("id"),
                            "message": message,
                            "channel_id": elem.get("channel_id"),
                            "author": elem.get("author"),
                            "timestamp": message_time,
                            "to_message": elem.get("referenced_message", {}).get("content"),
                            "to_user": elem.get("referenced_message", {}).get("author", {}).get("username")
                        }
                    )
        if messages:
            result.update({"messages": messages})
        if replies:
            replies: List[dict] = await self.__update_replies_to_redis(new_replies=replies)
            result.update({"replies": replies})

        return result

    @logger.catch
    async def __update_replies_to_redis(self, new_replies: list) -> list:
        """Возвращает разницу между старыми и новыми данными в редисе,
        записывает полные данные в редис"""

        total_replies: List[dict] = await RedisInterface(telegram_id=self.__datastore.telegram_id).load()
        old_messages: list = list(map(lambda x: x.get("message_id"), total_replies))
        result: List[dict] = [
            elem
            for elem in new_replies
            if elem.get("message_id") not in old_messages
        ]

        total_replies.extend(result)
        await RedisInterface(telegram_id=self.__datastore.telegram_id).save(data=total_replies)

        return result

    def __replies_filter(self, elem: dict) -> dict:
        """Возвращает реплаи не из нашего села."""

        result = {}
        ref_messages: dict = elem.get("referenced_message", {})
        if ref_messages:
            ref_messages_author: dict = ref_messages.get("author", {})
            if ref_messages_author:
                reply_for_author_id: str = ref_messages_author.get("id", '')
                mentions: tuple = tuple(
                    filter(
                        lambda x: int(x.get("id", '')) == int(self.__datastore.my_discord_id),
                        elem.get("mentions", [])
                    )
                )
                author: str = elem.get("author", {}).get("username", '')
                author_id: str = elem.get("author", {}).get("id", '')
                message_for_me: bool = reply_for_author_id == self.__datastore.my_discord_id
                if any(mentions) or message_for_me:
                    if author_id not in Token.get_all_discord_id(token=self.__datastore.token):
                        result.update({
                            "token": self.__datastore.token,
                            "author": author,
                            "text": elem.get("content", ''),
                            "message_id": elem.get("id", '')
                        })

        return result

    @classmethod
    async def __check_token(cls, token: str, proxy: str, channel: int) -> str:
        """Returns valid token else 'bad token'"""

        result: str = 'bad token'
        status: int = await cls._send_get_request(token=token, proxy=proxy, channel=channel)
        if status == 200:
            result = token
        elif status == 407:
            if not Proxy.update_proxies_for_owners(proxy):
                return 'no proxies'

        return result

    @classmethod
    async def _send_get_request(cls, proxy: str, token: str = '', channel: int = 0) -> int:
        """Отправляет запрос через прокси, возвращает статус код ответа"""

        async with aiohttp.ClientSession() as session:
            url: str = "https://www.google.com"
            if token:
                session.headers['authorization']: str = token
                limit: int = 1
                url: str = TokenDataStore.get_channel_url() + f'{channel}/messages?limit={limit}'
            proxy_data = f"http://{PROXY_USER}:{PROXY_PASSWORD}@{proxy}/"
            try:
                async with session.get(
                        url=url, proxy=proxy_data, ssl=False, timeout=10
                ) as response:
                    return response.status
            except cls.__EXCEPTIONS as err:
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


class MessageSender:
    """Отправляет сообщение в дискорд-канал в ответ на сообщение
    связанного токена
    Возвращает сообщение об ошибке или об успехе"""

    @logger.catch
    def __init__(self, datastore: 'TokenDataStore'):
        self.__datastore: 'TokenDataStore' = datastore
        self.__answer: dict = {}

    @logger.catch
    async def send_message(self, text: str = '') -> dict:
        """Отправляет данные в канал дискорда, возвращает результат отправки."""

        data: dict = await self.__prepare_data(text=text)
        await self.__send_data(data=data)
        Token.update_token_time(token=self.__datastore.token)

        return self.__answer

    @logger.catch
    async def __prepare_data(self, text: str = '') -> dict:
        """Возвращает сформированные данные для отправки в дискорд"""

        if not text:
            text: str = Vocabulary.get_message()
            if text == "Vocabulary error":
                self.__answer = {"status_code": -2, "data": {"message": text}}
        data = {
            "content": text,
            "tts": "false",
        }
        if self.__datastore.current_message_id:
            data.update({
                "content": text,
                "tts": "false",
                "message_reference":
                    {
                        "guild_id": self.__datastore.guild,
                        "channel_id": self.__datastore.channel,
                        "message_id": self.__datastore.current_message_id
                    },
                "allowed_mentions":
                    {
                        "parse": [
                            "users",
                            "roles",
                            "everyone"
                        ],
                        "replied_user": "false"
                    }
            })

        return data

    async def __typing(self, proxies: dict) -> None:
        """Имитирует "Пользователь печатает" в чате дискорда."""

        response = requests.post(
            f'https://discord.com/api/v9/channels/{self.__datastore.channel}/typing',
            headers={
                "Authorization": self.__datastore.token,
                "Content-Length": "0"
            },
            proxies=proxies
        )
        if response.status_code != 204:
            logger.warning(f"Typing: {response.status_code}")
        await asyncio.sleep(2)

    @logger.catch
    async def __send_data(self, data) -> None:
        """Отправляет данные в дискорд канал"""

        session = requests.Session()
        session.headers['authorization'] = self.__datastore.token
        url = self.__datastore.get_channel_url() + f'{self.__datastore.channel}/messages?'
        proxies = {
            "http": f"http://{PROXY_USER}:{PROXY_PASSWORD}@{self.__datastore.proxy}/",
        }
        try:
            await self.__typing(proxies=proxies)
            response = session.post(url=url, json=data, proxies=proxies)
            status_code = response.status_code
            if status_code == 200:
                data: dict = {}
            elif status_code == 407:
                Proxy.update_proxies_for_owners(self.__datastore.proxy)
            else:
                logger.error(f"F: __send_data_to_api error: {status_code}: {response.text}")
                try:
                    data: dict = response.json()
                except JSONDecodeError as err:
                    error_text = "F: __send_data_to_api: JSON ERROR:"
                    logger.error(error_text, err)
                    status_code = -1
                    data: dict = {"message": error_text}
        except requests.exceptions.ProxyError as err:
            logger.error(f"F: _send_data Error: {err}")
            status_code = 407

        self.__answer = {"status_code": status_code, "data": data}


class TokenDataStore:
    """
    Класс для хранения текущих данных для отправки и получения сообщений дискорда

    Methods
        check_user_data
        save_token_data
    """

    __DISCORD_BASE_URL: str = f'https://discord.com/api/v9/channels/'

    def __init__(self, telegram_id: str):
        self.telegram_id: str = telegram_id
        self.__CURRENT_MESSAGE_ID: int = 0
        self.__DISCORD_USER_TOKEN: str = ''
        self.__PROXY: str = ''
        self.__CHANNEL: int = 0
        self.__GUILD: int = 0
        self.__TOKEN_COOLDOWN: int = 0
        self.__MATE_DISCORD_ID: str = ''
        self.__DELAY: int = 0
        self.__MY_DISCORD_ID: str = ''

    def create_datastore_data(self, token: str):
        self.token: str = token
        token_data: dict = Token.get_info_by_token(token)
        self.proxy: str = token_data.get("proxy")
        self.channel: int = token_data.get("channel")
        self.guild: int = token_data.get("guild")
        self.cooldown: int = token_data.get("cooldown")
        self.mate_id: str = token_data.get("mate_id")
        self.my_discord_id: str = token_data.get("discord_id")

    @classmethod
    def get_channel_url(cls) -> str:
        return cls.__DISCORD_BASE_URL

    @property
    def my_discord_id(self) -> str:
        return self.__MY_DISCORD_ID

    @my_discord_id.setter
    def my_discord_id(self, my_discord_id: str):
        self.__MY_DISCORD_ID = my_discord_id

    @property
    def mate_id(self) -> str:
        return self.__MATE_DISCORD_ID

    @mate_id.setter
    def mate_id(self, mate_id: str):
        self.__MATE_DISCORD_ID = mate_id

    @property
    def last_message_time(self) -> float:
        return self.__TOKEN_COOLDOWN + 120

    @property
    def delay(self) -> int:
        return self.__DELAY

    @delay.setter
    def delay(self, delay: int):
        self.__DELAY = delay

    @property
    def cooldown(self) -> int:
        return self.__TOKEN_COOLDOWN

    @cooldown.setter
    def cooldown(self, cooldown: int):
        self.__TOKEN_COOLDOWN = cooldown

    @property
    def current_message_id(self) -> int:
        return self.__CURRENT_MESSAGE_ID

    @current_message_id.setter
    def current_message_id(self, message_id: int):
        self.__CURRENT_MESSAGE_ID = message_id

    @property
    def channel(self) -> str:
        channel = self.__CHANNEL

        return channel if channel else 'no channel'

    @channel.setter
    def channel(self, channel: str):
        self.__CHANNEL = channel

    @property
    def guild(self) -> str:
        guild = self.__GUILD

        return guild if guild else 'no guild'

    @guild.setter
    def guild(self, guild: str):
        self.__GUILD = guild

    @property
    def token(self) -> str:
        spam = self.__DISCORD_USER_TOKEN

        return spam if spam else 'no token'

    @token.setter
    def token(self, token: str):
        self.__DISCORD_USER_TOKEN = token

    @property
    def proxy(self) -> str:
        return self.__PROXY if self.__PROXY else 'no proxy'

    @proxy.setter
    def proxy(self, proxy: str) -> None:
        self.__PROXY = proxy


class InstancesStorage:
    """
    Класс для хранения экземпляров классов данных (ID сообщения в дискорде, время и прочая)
    для каждого пользователя телеграма.
    Инициализируется при запуске бота.
    """
    # TODO сделать синглтон

    def __init__(self):
        self.__instance = {}

    @logger.catch
    def get_instance(self, telegram_id: str) -> 'UserData':
        """Возвращает текущий экземпляр класса для пользователя'"""

        return self.__instance.get(telegram_id, {})

    @logger.catch
    def add_or_update(self, telegram_id: str, data: 'UserData') -> None:
        """Сохраняет экземпляр класса пользователя"""

        self.__instance.update(
            {
                telegram_id: data
            }
        )

    def mute(self, telegram_id):
        user_class: 'UserData' = self.get_instance(telegram_id=telegram_id)
        if user_class:
            user_class.silence = True
            return True

    def unmute(self, telegram_id):
        user_class: 'UserData' = self.get_instance(telegram_id=telegram_id)
        if user_class:
            user_class.silence = False
            return True


class UserData:

    def __init__(self, message: Message, mute: bool = False) -> None:
        self.message: 'Message' = message
        self.user_telegram_id: str = str(self.message.from_user.id)
        self.__silence: bool = mute
        self.datastore: Optional['TokenDataStore'] = None

    @logger.catch
    async def lets_play(self) -> None:
        """Show must go on
        Запускает рабочий цикл бота, проверяет ошибки."""

        while User.get_is_work(telegram_id=self.user_telegram_id):
            if await self.is_expired_user_deactivated():
                break
            self.datastore: 'TokenDataStore' = TokenDataStore(self.user_telegram_id)
            users_data_storage.add_or_update(telegram_id=self.user_telegram_id, data=self)
            self.datastore.silence = False
            message_manager: 'MessageReceiver' = MessageReceiver(datastore=self.datastore)

            discord_data: dict = await message_manager.get_message()
            if not discord_data:
                await send_report_to_admins(
                    "Произошла какая то чудовищная ошибка в функции lets_play.")
                break
            token_work: bool = discord_data.get("work")

            replies: List[dict] = discord_data.get("replies", [])
            if replies:
                await self.send_replies(message=self.message, replies=replies)
            if not token_work:
                text: str = await self.get_error_text(
                    datastore=self.datastore, discord_data=discord_data)
                if text == 'stop':
                    break
                elif text != 'ok':
                    if not self.__silence:
                        await self.message.answer(text, reply_markup=cancel_keyboard())
                logger.info(f"PAUSE: {self.datastore.delay + 1}")
                if not datetime.datetime.now().minute % 10:
                    self.form_token_pairs(unpair=True)
                    logger.info(f"Время распределять токены!")

                await asyncio.sleep(self.datastore.delay + 1)
                self.datastore.delay = 0
                if not self.__silence:
                    await self.message.answer("Начинаю работу.", reply_markup=cancel_keyboard())
            await asyncio.sleep(1 / 1000)

    @logger.catch
    async def send_replies(self, replies: list):
        """Отправляет реплаи из дискорда в телеграм с кнопкой Ответить"""

        result = []
        for reply in replies:
            answered: bool = reply.get("answered", False)
            if not answered:
                answer_keyboard: 'InlineKeyboardMarkup' = InlineKeyboardMarkup(row_width=1)
                author: str = reply.get("author")
                reply_id: str = reply.get("message_id")
                reply_text: str = reply.get("text")
                reply_to_author: str = reply.get("to_user")
                reply_to_message: str = reply.get("to_message")
                answer_keyboard.add(InlineKeyboardButton(
                    text="Ответить",
                    callback_data=f'reply_{reply_id}'
                ))
                await self.message.answer(
                    f"Вам пришло сообщение из ДИСКОРДА:"
                    f"\nКому: {reply_to_author}"
                    f"\nНа сообщение: {reply_to_message}"
                    f"\nОт: {author}"
                    f"\nText: {reply_text}",
                    reply_markup=answer_keyboard
                )
                result.append(reply)

        return result

    @logger.catch
    async def get_error_text(self, discord_data: dict, datastore: 'TokenDataStore') -> str:
        """Обработка ошибок от сервера"""

        text: str = discord_data.get("message", "ERROR")
        token: str = discord_data.get("token")
        answer: dict = discord_data.get("answer", {})
        data: dict = answer.get("data", {})
        status_code: int = answer.get("status_code", 0)
        sender_text: str = answer.get("message", "SEND_ERROR")
        discord_code_error: int = answer.get("data", {}).get("code", 0)

        result: str = 'ok'

        if text == "no pairs":
            pairs_formed: int = self.form_token_pairs(unpair=False)
            if not pairs_formed:
                await self.message.answer("Не смог сформировать пары токенов.")
                result = 'stop'
        elif status_code == -1:
            error_text = sender_text
            await self.message.answer("Ошибка десериализации отправки ответа.")
            await send_report_to_admins(error_text)
            result = "stop"
        elif status_code == -2:
            await self.message.answer("Ошибка словаря.", reply_markup=user_menu_keyboard())
            await send_report_to_admins("Ошибка словаря.")
            result = "stop"
        elif status_code == 400:
            if discord_code_error == 50035:
                sender_text = 'Сообщение для ответа удалено из дискорд канала.'
            else:
                result = "stop"
            await send_report_to_admins(sender_text)
        elif status_code == 401:
            if discord_code_error == 0:
                await self.message.answer("Сменился токен."
                                     f"\nToken: {token}")
            else:
                await self.message.answer(
                    "Произошла ошибка данных. "
                    "Убедитесь, что вы ввели верные данные. Код ошибки - 401.",
                    reply_markup=user_menu_keyboard()
                )
            result = "stop"
        elif status_code == 403:
            if discord_code_error == 50013:
                await self.message.answer(
                    "Не могу отправить сообщение для токена. (Ошибка 403 - 50013)"
                    "Токен в муте."
                    f"\nToken: {token}"
                    f"\nGuild: {datastore.guild}"
                    f"\nChannel: {datastore.channel}"
                )
            elif discord_code_error == 50001:
                Token.delete_token(token=token)
                await self.message.answer(
                    "Не могу отправить сообщение для токена. (Ошибка 403 - 50001)"
                    "Токен забанили."
                    f"\nТокен: {token} удален."
                    f"\nФормирую новые пары.",
                    reply_markup=user_menu_keyboard()
                )
                self.form_token_pairs(unpair=False)
            else:
                await self.message.answer(f"Ошибка {status_code}: {data}")
        elif status_code == 404:
            if discord_code_error == 10003:
                await self.message.answer(
                    "Ошибка отправки сообщения. Неверный канал. (Ошибка 404 - 10003)"
                    f"\nToken: {token}"
                )
            else:
                await self.message.answer(f"Ошибка {status_code}: {data}")
        elif status_code == 407:
            await self.message.answer(
                "Ошибка прокси. Обратитесь к администратору. Код ошибки 407.",
                reply_markup=ReplyKeyboardRemove()
            )
            await send_report_to_admins(f"Ошибка прокси. Время действия proxy истекло.")
            result = "stop"
        elif status_code == 429:
            if discord_code_error == 20016:
                cooldown: int = int(data.get("retry_after", None))
                if cooldown:
                    cooldown += datastore.cooldown + 2
                    Token.update_token_cooldown(token=token, cooldown=cooldown)
                    Token.update_mate_cooldown(token=token, cooldown=cooldown)
                    datastore.delay = cooldown
                await self.message.answer(
                    "Для данного токена сообщения отправляются чаще, чем разрешено в канале."
                    f"\nToken: {token}"
                    f"\nВремя скорректировано. Кулдаун установлен: {cooldown} секунд"
                )
            else:
                await self.message.answer(f"Ошибка: "
                                          f"{status_code}:{discord_code_error}:{sender_text}")
        elif status_code == 500:
            error_text = (
                f"Внутренняя ошибка сервера Дискорда. "
                f"\nГильдия:Канал: {datastore.guild}:{datastore.channel} "
                f"\nПауза 10 секунд. Код ошибки - 500."
            )
            await self.message.answer(error_text)
            await send_report_to_admins(error_text)
            datastore.delay = 10
        else:
            result = text

        return result

    @logger.catch
    def form_token_pairs(self, unpair: bool = False) -> int:
        """Формирует пары из свободных токенов если они в одном канале"""

        if unpair:
            User.delete_all_pairs(telegram_id=self.user_telegram_id)
        free_tokens: Tuple[Tuple[str, list]] = Token.get_all_free_tokens(telegram_id=self.user_telegram_id)
        formed_pairs: int = 0
        for channel, tokens in free_tokens:
            while len(tokens) > 1:
                random.shuffle(tokens)
                formed_pairs += Token.make_tokens_pair(tokens.pop(), tokens.pop())
        logger.info(f"Pairs formed: {formed_pairs}")

        return formed_pairs

    @logger.catch
    async def is_expired_user_deactivated(self) -> bool:
        """Удаляет пользователя с истекшим сроком действия.
        Возвращает True если деактивирован."""

        user_not_expired: bool = User.check_expiration_date(telegram_id=self.user_telegram_id)
        user_is_admin: bool = User.is_admin(telegram_id=self.user_telegram_id)
        if not user_not_expired and not user_is_admin:
            await self.message.answer(
                "Время подписки истекло. Ваш аккаунт деактивирован, токены удалены.",
                reply_markup=ReplyKeyboardRemove()
            )
            User.delete_all_tokens(telegram_id=self.user_telegram_id)
            User.deactivate_user(telegram_id=self.user_telegram_id)
            text = (
                f"Время подписки {self.user_telegram_id} истекло, "
                f"пользователь декативирован, его токены удалены"
            )
            logger.info(text)
            await send_report_to_admins(text)
            return True

        return False

    @property
    def silence(self) -> bool:
        return self.__silence

    @silence.setter
    def silence(self, silence: bool):
        if not isinstance(silence, bool):
            raise TypeError("Silence must be boolean.")
        self.__silence = silence


# initialization user data storage
users_data_storage = InstancesStorage()
