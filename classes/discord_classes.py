import datetime
import random
from json import JSONDecodeError
from typing import List, Tuple, Optional

import asyncio

import aiohttp
import requests
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove

from classes.proxy_checker import ProxyChecker
from classes.request_sender import RequestSender
from classes.vocabulary import Vocabulary
from classes.token_datastorage import TokenDataStore
from config import logger, PROXY_USER, PROXY_PASSWORD, DISCORD_BASE_URL
from utils import send_report_to_admins
from keyboards import cancel_keyboard, user_menu_keyboard
from models import User, Token
from classes.redis_interface import RedisDB
from classes.open_ai import OpenAI


class MessageReceiver:

    """Выбирает токен для отправки сообщения и вызывает метод вызова сообщения,
    проверяет его ответ, и, если есть свободные токены - повторяет процесс.
    При ошибке возвращает ее в телеграм"""

    @logger.catch
    def __init__(self, datastore: 'TokenDataStore'):
        self.__datastore: 'TokenDataStore' = datastore

    @logger.catch
    async def get_message(self) -> dict:
        """Получает данные из АПИ, выбирает случайное сообщение и возвращает ID сообщения
        и само сообщение"""

        # TODO сделать список в редис, куда складывать айдишники всех сообщений, на которые ответили
        # TODO Вынести работу с отправкой запросов в отдельный класс и написать обработку ошибок там
        # TODO Сделать флаг автоответа (если флаг стоит - то отвечает бот Давинчи, иначе -
        #  отправлять в телеграм юзеру
        # TODO выделить реплаи и работу с ними в отдельный класс
        # TODO Разобрать данный класс на несколько
        # TODO Разделение создания экземпляров - создавать там, где используются, а не еще где то.

        result = {"work": False}
        user_message, message_id = await self.__get_user_message_from_redis()

        filtered_data: dict = await self.__get_filtered_data()
        if filtered_data:
            replies: List[dict] = filtered_data.get("replies", [])
            if replies:
                result.update({"replies": replies})

        if message_id:
            self.__datastore.current_message_id = message_id
        elif filtered_data:
            self.__datastore.current_message_id = filtered_data.get("last_message_id")
        text_to_send: str = user_message if user_message else ''
        answer: dict = await MessageSender(datastore=self.__datastore, text=text_to_send).send_message()
        if not answer:
            logger.error("F: get_message ERROR: NO ANSWER ERROR")
            result.update({"message": "ERROR"})
            return result
        elif answer.get("status_code") != 200:
            result.update({"answer": answer, "token": self.__datastore.token})
            return result

        self.__datastore.current_message_id = 0
        result.update({"work": True})

        timer: float = 7 + random.randint(0, 6)
        logger.info(f"Пауза между отправкой сообщений: {timer}")
        await asyncio.sleep(timer)

        return result

    @logger.catch
    async def __get_user_message_from_redis(self) -> Tuple[str, int]:
        """Возвращает данные из Редиса"""

        answer: str = ''
        message_id = 0
        redis_data: List[dict] = await RedisDB(redis_key=self.__datastore.telegram_id).load()
        if not redis_data:
            return answer, message_id

        for elem in redis_data:
            if not isinstance(elem, dict):
                continue
            answered = elem.get("answered", False)
            if not answered:
                if elem.get("token") == self.__datastore.token:
                    answer = elem.get("answer_text", '')
                    if answer:
                        message_id = elem.get("message_id", 0)
                        elem.update({"answered": True})
                        await RedisDB(redis_key=self.__datastore.telegram_id).save(data=redis_data)
                        break

        return answer, message_id

    @logger.catch
    async def __get_filtered_data(self) -> dict:
        """Отправляет запрос к АПИ"""

        data = []
        response: 'aiohttp.ClientResponse' = await RequestSender(datastore=self.__datastore).get_data_from_channel()
        if response:
            data: List[dict] = await response.json()
        result: dict = await self.__data_filter(data=data)

        return result

    @logger.catch
    async def __data_filter(self, data: List[dict]) -> dict:
        """Фильтрует полученные данные"""

        messages = []
        replies = []
        result = {}
        for elem in data:

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
                    spam: dict = {
                            "id": elem.get("id"),
                            "timestamp": message_time,
                        }
                    messages.append(spam)
        last_message_id: int = await self.__get_last_message_id(data=messages)
        result.update({"last_message_id": last_message_id})
        replies: List[dict] = await self.__update_replies_to_redis(new_replies=replies)
        result.update({"replies": replies})

        return result

    @logger.catch
    async def __get_last_message_id(self, data: list) -> int:
        if not data:
            return 0
        return int(max(data, key=lambda x: x.get("timestamp"))["id"])

    @logger.catch
    async def __update_replies_to_redis(self, new_replies: list) -> list:
        """Возвращает разницу между старыми и новыми данными в редисе,
        записывает полные данные в редис"""

        total_replies: List[dict] = await RedisDB(redis_key=self.__datastore.telegram_id).load()
        old_messages: list = list(map(lambda x: x.get("message_id"), total_replies))
        result: List[dict] = [
            elem
            for elem in new_replies
            if elem.get("message_id") not in old_messages
        ]

        total_replies.extend(result)
        await RedisDB(redis_key=self.__datastore.telegram_id).save(data=total_replies)

        return result

    @logger.catch
    def __replies_filter(self, elem: dict) -> dict:
        """Возвращает реплаи не из нашего села."""


        result = {}
        ref_messages: dict = elem.get("referenced_message", {})
        if not ref_messages:
            return result
        ref_messages_author: dict = ref_messages.get("author", {})
        if not ref_messages_author:
            return result
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
            all_discord_tokens: List[str] = Token.get_all_discord_id(token=self.__datastore.token)
            if author_id not in all_discord_tokens:
                result.update({
                    "token": self.__datastore.token,
                    "author": author,
                    "text": elem.get("content", ''),
                    "message_id": elem.get("id", ''),
                    "to_message": ref_messages.get("content"),
                    "to_user": ref_messages.get("author", {}).get("username")
                })

        return result


class MessageSender:
    """Отправляет сообщение в дискорд-канал в ответ на сообщение
    связанного токена
    Возвращает сообщение об ошибке или об успехе"""

    def __init__(self, datastore: 'TokenDataStore', text: str = ''):
        self.__datastore: 'TokenDataStore' = datastore
        self.__answer: dict = {}
        self.__data_for_send: dict = {}
        self.__text: str = text

    @logger.catch
    async def send_message(self) -> dict:
        """Отправляет данные в канал дискорда, возвращает результат отправки."""

        await self.__prepare_data()
        if self.__data_for_send:
            await self.__send_data()
            Token.update_token_time(token=self.__datastore.token)

        return self.__answer

    @logger.catch
    async def __get_text_from_vocabulary(self) -> str:
        text: str = Vocabulary.get_message()
        if text == "Vocabulary error":
            self.__answer = {"status_code": -2, "data": {"message": text}}
            return ''
        await RedisDB(redis_key=self.__datastore.mate_id).save(data=[text])
        return text

    @logger.catch
    async def __prepare_message_text(self) -> None:
        mate_message: list = await RedisDB(redis_key=self.__datastore.my_discord_id).load()
        logger.debug(f"From mate: {mate_message}")
        if mate_message:
            self.__text: str = OpenAI().get_answer(mate_message[0].strip())
            await RedisDB(redis_key=self.__datastore.my_discord_id).delete(mate_id=self.__datastore.mate_id)
        if not self.__text:
            self.__text: str = await self.__get_text_from_vocabulary()

    @logger.catch
    def __roll_the_dice(self) -> bool:
        return random.randint(1, 100) <= 10

    async def __get_text(self) -> None:
        if self.__text:
            return
        if self.__roll_the_dice():
            logger.debug("Random message!")
            self.__datastore.current_message_id = 0
            self.__text = await self.__get_text_from_vocabulary()
            return
        await self.__prepare_message_text()

    @logger.catch
    async def __prepare_data(self) -> None:
        """Возвращает сформированные данные для отправки в дискорд"""

        await self.__get_text()
        if not self.__text:
            return
        logger.debug(f"Final text: {self.__text}")
        self.__data_for_send = {
            "content": self.__text,
            "tts": "false",
        }
        if self.__datastore.current_message_id:
            self.__data_for_send.update({
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

    @logger.catch
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
            logger.warning(f"Typing: {response.status_code}: {response.text}")
        await asyncio.sleep(2)

    @logger.catch
    async def __send_data(self) -> None:
        """Отправляет данные в дискорд канал"""

        session = requests.Session()
        session.headers['authorization'] = self.__datastore.token
        url = DISCORD_BASE_URL + f'{self.__datastore.channel}/messages?'
        proxies = {
            "http": f"http://{PROXY_USER}:{PROXY_PASSWORD}@{self.__datastore.proxy}/",
            "https": f"http://{PROXY_USER}:{PROXY_PASSWORD}@{self.__datastore.proxy}/"
        }
        answer_data: dict = {}
        try:
            await self.__typing(proxies=proxies)
            await asyncio.sleep(1)
            await self.__typing(proxies=proxies)
            # logger.debug(f"Sending message:"
            #              f"\n\tUSER: {self.__datastore.telegram_id}"
            #              f"\n\tGUILD/CHANNEL: {self.__datastore.guild}/{self.__datastore.channel}"
            #              f"\n\tTOKEN: {self.__datastore.token}"
            #              f"\n\tDATA: {self.__data_for_send}"
            #              f"\n\tPROXIES: {self.__datastore.proxy}")
            response = session.post(url=url, json=self.__data_for_send, proxies=proxies)
            status_code = response.status_code
            if status_code != 200:
                logger.error(f"F: __send_data_to_api error: {status_code}: {response.text}")
                try:
                    answer_data: dict = response.json()
                except JSONDecodeError as err:
                    error_text = "F: __send_data_to_api: JSON ERROR:"
                    logger.error(error_text, err)
                    status_code = -1
                    answer_data: dict = {"message": error_text}
        except (requests.exceptions.ProxyError, requests.exceptions.ConnectionError) as err:
            logger.error(f"F: _send_data Error: {err}")
            status_code = 407
        self.__answer = {"status_code": status_code, "data": answer_data}
        if status_code == 407:
            new_proxy: str = await ProxyChecker.get_proxy(self.__datastore.telegram_id)
            if new_proxy == 'no proxies':
                return
            self.__datastore.proxy = new_proxy
            await self.__send_data()


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

    @logger.catch
    def mute(self, telegram_id):
        user_class: 'UserData' = self.get_instance(telegram_id=telegram_id)
        if user_class:
            user_class.silence = True
            return True

    @logger.catch
    def unmute(self, telegram_id):
        user_class: 'UserData' = self.get_instance(telegram_id=telegram_id)
        if user_class:
            user_class.silence = False
            return True


class UserData:

    """Класс управления токенами и таймингами.
    Methods:
        lets_play
        form_token_pair
        is_expired_user_deactivated
    """

    def __init__(self, message: Message, mute: bool = False) -> None:
        self.message: 'Message' = message
        self.__username: str = message.from_user.username
        self.user_telegram_id: str = str(self.message.from_user.id)
        self.__silence: bool = mute
        self.__current_tokens_list: List[dict] = []
        self.__workers: List[str] = []
        self.__datastore: Optional['TokenDataStore'] = None

    @logger.catch
    async def lets_play(self) -> None:
        """Show must go on
        Запускает рабочий цикл бота, проверяет ошибки."""

        while User.get_is_work(telegram_id=self.user_telegram_id):
            logger.debug(f"\tUSER: {self.__username}:{self.user_telegram_id} - Game begin.")
            if await self.is_expired_user_deactivated():
                break
            self.__datastore: 'TokenDataStore' = TokenDataStore(self.user_telegram_id)
            users_data_storage.add_or_update(telegram_id=self.user_telegram_id, data=self)
            if not await self.__is_token_ready():
                break

            message_manager: 'MessageReceiver' = MessageReceiver(datastore=self.__datastore)
            discord_data: dict = await message_manager.get_message()
            if not discord_data:
                await send_report_to_admins(
                    "Произошла какая то чудовищная ошибка в функции lets_play."
                    f"discord_data: {discord_data}\n")
                break
            token_work: bool = discord_data.get("work")
            replies: List[dict] = discord_data.get("replies", [])
            if replies:
                await self.__send_replies(replies=replies)
            if not token_work:
                text: str = await self.__get_error_text(discord_data=discord_data)
                if text == 'stop':
                    break
                elif text != 'ok':
                    if not self.__silence:
                        await self.message.answer(text, reply_markup=cancel_keyboard())
            await asyncio.sleep(1 / 1000)
        logger.debug("Game over.")

    @logger.catch
    async def __send_text(self, text: str, keyboard=None, check_silence: bool = False) -> None:
        """Отправляет текст и клавиатуру пользователю если он не в тихом режиме."""

        if check_silence and self.__silence:
            return
        if not keyboard:
            await self.message.answer(text)
            return
        await self.message.answer(text, reply_markup=keyboard)

    @logger.catch
    async def __is_token_ready(self) -> bool:

        if not self.__workers:
            self.form_token_pairs(unpair=True)
            self.__current_tokens_list = await self.__get_tokens_list()
            if not self.__current_tokens_list:
                await self.__send_text(text="Не смог сформировать пары токенов.", keyboard=user_menu_keyboard())
                return False
            await self.__get_workers()
        if await self.__get_worker_from_list():
            return True
        message: str = await self.__get_all_tokens_busy_message()
        await self.__send_text(text=message, check_silence=True)
        await self.__sleep()
        return True

    @logger.catch
    async def __sleep(self):
        logger.info(f"PAUSE: {self.__datastore.delay + 1}")
        await asyncio.sleep(self.__datastore.delay + 1)
        self.__datastore.delay = 0
        await self.__send_text(text="Начинаю работу.", keyboard=cancel_keyboard(), check_silence=True)

    @logger.catch
    async def __get_tokens_list(self) -> list:
        """Возвращает список всех токенов пользователя."""

        return Token.get_all_related_user_tokens(telegram_id=self.__datastore.telegram_id)

    @logger.catch
    async def __get_workers(self) -> None:
        """Возвращает список токенов, которые не на КД"""
        self.__workers = [
            key
            for elem in self.__current_tokens_list
            for key, value in elem.items()
            if await self.__get_current_time() > value["time"] + value["cooldown"]
        ]

    @logger.catch
    async def __get_worker_from_list(self) -> bool:
        """Возвращает токен для работы"""

        if not self.__workers:
            return False
        random.shuffle(self.__workers)
        random_token: str = self.__workers.pop()
        self.__datastore.create_datastore_data(random_token)
        return True

    @logger.catch
    async def __get_current_time(self) -> int:
        """Возвращает текущее время (timestamp) целое."""

        return int(datetime.datetime.now().timestamp())

    @logger.catch
    async def __get_all_tokens_busy_message(self) -> str:
        min_token_data = {}
        for elem in self.__current_tokens_list:
            min_token_data: dict = min(elem.items(), key=lambda x: x[1].get('time'))
        token: str = tuple(min_token_data)[0]
        self.__datastore.create_datastore_data(token)
        min_token_time: int = Token.get_time_by_token(token)
        delay: int = self.__datastore.cooldown - abs(min_token_time - await self.__get_current_time())
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

        return f"Все токены отработали. Следующий старт через {delay} {text}."

    @logger.catch
    async def __send_replies(self, replies: list):
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
    async def __get_error_text(self, discord_data: dict) -> str:
        """Обработка ошибок от сервера"""

        text: str = discord_data.get("message", "ERROR")
        token: str = discord_data.get("token")
        answer: dict = discord_data.get("answer", {})
        data: dict = answer.get("data", {})
        status_code: int = answer.get("status_code", 0)
        sender_text: str = answer.get("message", "SEND_ERROR")
        discord_code_error: int = answer.get("data", {}).get("code", 0)

        result: str = 'ok'

        if status_code == -1:
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
                    f"\nGuild: {self.__datastore.guild}"
                    f"\nChannel: {self.__datastore.channel}"
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
                    cooldown += self.__datastore.cooldown + 2
                    Token.update_token_cooldown(token=token, cooldown=cooldown)
                    Token.update_mate_cooldown(token=token, cooldown=cooldown)
                    self.__datastore.delay = cooldown
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
                f"\nГильдия:Канал: {self.__datastore.guild}:{self.__datastore.channel} "
                f"\nПауза 10 секунд. Код ошибки - 500."
            )
            await self.message.answer(error_text)
            await send_report_to_admins(error_text)
            self.__datastore.delay = 10
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
                first_token = tokens.pop()
                second_token = tokens.pop()
                # if DEBUG:
                #     first_token_instance: 'Token' = Token.get_by_id(first_token)
                #     second_token_instance: 'Token' = Token.get_by_id(second_token)
                #     logger.debug(f"Pairs formed: "
                #                  f"\nFirst: {first_token_instance.token}"
                #                  f"\nSecond: {second_token_instance.token}")
                formed_pairs += Token.make_tokens_pair(first_token, second_token)

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
