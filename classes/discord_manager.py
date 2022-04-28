import datetime
import random
from typing import List, Optional, Tuple
from collections import namedtuple

import asyncio

from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from classes.errors_sender import ErrorsSender
from classes.message_manager import MessageManager
from classes.message_sender import MessageSender
from classes.open_ai import OpenAI
from classes.replies import RepliesManager
from classes.token_datastorage import TokenData

from config import logger
from classes.db_interface import DBI
from keyboards import user_menu_keyboard


def check_working(func):
    async def wrapper(*args, **kwargs):
        name: str = func.__name__
        if args and hasattr(args[0].__class__, name):
            is_working: bool = getattr(args[0], "is_working")
            if is_working:
                # logger.debug(f"\t{name}: OK")
                return await func(*args, **kwargs)
        # logger.debug(f"\t{name}: FAIL")
        return

    return wrapper


class DiscordManager:
    """Bot work manager. Checking tokens data, getting and sending requests
    to discord.

    Methods:
        lets_play - start bot working

    Attributes:
        message: 'Message' - instance of aiogram Message class
        silence: bool - flag for silence mode
        is_working: bool - flag for check working mode
        auto_answer: bool - flag for OpenAI autoansweri to replies from discord
        reboot: bool - if True - dont start working than server will not rebooted yet
        delay: int - time for sleep after all tokens worked
        datastore: 'TokenData' - instance of TokenData class
    """

    def __init__(self, message: Message, mute: bool = False) -> None:
        self.message: 'Message' = message
        self.datastore: Optional['TokenData'] = None
        self.is_working: bool = False
        self.delay: int = 0
        self.auto_answer: bool = False
        self.reboot: bool = False
        self.__username: str = message.from_user.username
        self.__telegram_id: str = str(self.message.from_user.id)
        self.silence: bool = mute
        self.__related_tokens: List[namedtuple] = []
        self.__workers: List[str] = []

    @logger.catch
    async def lets_play(self) -> None:
        """Show must go on
        Запускает рабочий цикл бота, проверяет ошибки."""

        logger.info(f"\n\tUSER: {self.__username}: {self.__telegram_id} - Game begin.")
        await self._create_datastore()
        await self._make_all_token_ids()

        while self.is_working:
            await self._lets_play()
        logger.info("\n\tGame over.")

    async def __check_reboot(self) -> None:
        if self.reboot:
            await self.message.answer(
                "Ожидайте перезагрузки сервера.",
                reply_markup=user_menu_keyboard())
            self.is_working = False

    async def __get_full_info(self) -> str:
        return (
            f"\n\tUsername: {self.__username}"
            f"\n\tUser telegram id: {self.__telegram_id}"
            f"\n\tToken: {self.datastore.token}"
            f"\n\tProxy: {self.datastore.proxy}"
            f"\n\tDiscord ID: {self.datastore.my_discord_id}"
            f"\n\tMate discord id: {self.datastore.mate_id}"
            f"\n\tSilence: {self.silence}"
            f"\n\tAutoanswer: {self.auto_answer}"
            f"\n\tWorkers: {len(self.__workers)}/{len(self.__related_tokens)}"
            # f"\n\tRelated tokens: {self.__related_tokens}"
        )

    async def _check_user_active(self):
        user_deactivated: bool = await DBI.is_expired_user_deactivated(self.message)
        user_is_work: bool = await DBI.is_user_work(telegram_id=self.__telegram_id)
        if user_deactivated or not user_is_work:
            self.is_working = False

    @logger.catch
    async def _lets_play(self) -> None:
        await self.__check_reboot()
        await self._check_user_active()
        await self._get_working_data()
        await self._getting_messages()
        await self._send_replies()
        await self._sending_messages()
        await self._sleep()

    @logger.catch
    async def _create_datastore(self) -> None:
        self.datastore: 'TokenData' = TokenData(self.__telegram_id)

    @logger.catch
    async def _make_all_token_ids(self) -> None:
        self.datastore.all_tokens_ids = await DBI.get_all_discord_id(self.__telegram_id)
        if not self.datastore.all_tokens_ids:
            logger.debug(f"No all_tokens_ids.")
            return
        self.is_working = True

    @check_working
    @logger.catch
    async def _getting_messages(self) -> None:
        """Получает сообщения из чата и обрабатывает их
        Если удачно - перезаписывает кулдаун текущего токена"""

        await MessageManager(datastore=self.datastore).get_message()
        await DBI.update_token_last_message_time(token=self.datastore.token)
        await self.__update_token_last_message_time(token=self.datastore.token)

    @logger.catch
    def __replace_time_to_now(self, elem) -> namedtuple:
        return elem._replace(last_message_time=datetime.datetime.now())

    @logger.catch
    async def __update_token_last_message_time(self, token: str) -> None:
        """"""

        self.__related_tokens = [self.__replace_time_to_now(elem)
                                 if elem.token == token else elem
                                 for elem in self.__related_tokens]

    @check_working
    @logger.catch
    async def _sending_messages(self) -> None:
        """Отправляет сообщение в дискор и сохраняет данные об ошибках в
        словарь атрибута класса"""

        if not await MessageSender(datastore=self.datastore).send_message_to_discord():
            self.__workers = []
            channel_data: namedtuple = await DBI.get_channel(self.datastore.user_channel_pk)
            self.delay = 60
            if channel_data:
                self.delay = int(channel_data.cooldown)
            return
        self.datastore.current_message_id = 0

    @check_working
    @logger.catch
    async def _get_working_data(self) -> None:
        """Создает пары токенов, список работников и следующий рабочий токен."""

        if not self.__workers:
            await self.make_token_pairs(unpair=True)
            await self._make_workers_list()
        logger.debug(await self.__get_full_info())
        await self._get_worker_from_list()

    @check_working
    @logger.catch
    async def _sleep(self) -> None:
        """Спит на время ближайшего токена."""

        if self.__workers:
            return
        await self._get_delay()
        self.delay += random.randint(3, 7)
        logger.info(f"SLEEP PAUSE: {self.delay}")
        await self._send_delay_message()
        if self.delay <= 0:
            self.delay = 60
        timer: int = self.delay
        while timer > 0:
            timer -= 5
            if not self.is_working:
                return
            await asyncio.sleep(5)
        self.delay = 0

    @logger.catch
    def __get_max_message_time(self, elem: namedtuple) -> int:
        """Возвращает максимальное время фильтрации сообщения. Сообщения с временем меньше
        данного будут отфильтрованы"""

        return int(elem.last_message_time.timestamp()) + elem.cooldown

    @check_working
    @logger.catch
    async def _make_workers_list(self) -> None:
        """Возвращает список токенов, которые не на КД"""

        self.__workers = [
            elem.token
            for elem in self.__related_tokens
            if self.__get_current_timestamp() > self.__get_max_message_time(elem)
        ]

    @check_working
    @logger.catch
    async def _get_worker_from_list(self) -> None:
        """Возвращает токен для работы"""

        if not self.__workers:
            return
        random.shuffle(self.__workers)
        random_token: str = self.__workers.pop()
        await self._update_datastore(random_token)

    @logger.catch
    async def _update_datastore(self, token: str) -> None:
        """Обновляет данные datastore информацией о токене, полученной из БД"""

        token_data: namedtuple = await DBI.get_info_by_token(token)
        self.datastore.update_data(token=token, token_data=token_data)

    @logger.catch
    def __get_current_timestamp(self) -> int:
        """Возвращает текущее время (timestamp) целое."""

        return int(datetime.datetime.now().timestamp())

    @logger.catch
    async def __get_second_closest_token_time(self) -> namedtuple:
        """Возвращает время второго ближайшего токена"""

        return sorted(self.__related_tokens, key=lambda x: x.last_message_time)[1]

    @logger.catch
    async def _get_delay(self) -> None:
        """Сохраняет время паузы взяв его из второго в очереди на работу токена"""

        if self.delay:
            return
        token_data: namedtuple = await self.__get_second_closest_token_time()
        message_time: int = int(token_data.last_message_time.timestamp())
        cooldown: int = token_data.cooldown
        self.delay = cooldown - abs(message_time - self.__get_current_timestamp())

    @check_working
    @logger.catch
    async def _send_delay_message(self) -> None:
        """Отправляет сообщение что все токены заняты"""

        delay: int = self.delay
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
        text: str = f"Все токены отработали. Следующий старт через {delay} {text}."
        if not self.silence:
            await self.message.answer(text)

    @check_working
    @logger.catch
    async def _send_replies(self) -> None:
        """Отправляет реплаи из дискорда в телеграм с кнопкой Ответить
        либо отправляет сообщение в нейросеть, чтоб она ответила"""

        replyer: 'RepliesManager' = RepliesManager(self.__telegram_id)
        for elem in self.datastore.for_reply:
            if not elem.get("showed") and not elem.get("answered"):
                if self.auto_answer:
                    await self._auto_reply_with_davinchi(elem, replyer)
                else:
                    await self.__send_reply_to_telegram(elem)
                    await replyer.update_answered_or_showed(str(elem.get("message_id")))

    @logger.catch
    async def _auto_reply_with_davinchi(self, data: dict, replyer: 'RepliesManager') -> None:
        """Отвечает с на реплай с помощью ИИ и сохраняет изменнные данные в Редис
        Если ИИ не ответил - отправляет сообщение пользователю в обычном режиме"""

        reply_text: str = data.get("text")
        ai_reply_text: str = OpenAI(davinchi=True).get_answer(message=reply_text)
        if ai_reply_text:
            await replyer.update_answered_or_showed(
                message_id=str(data.get("message_id")), text=ai_reply_text)
            text: str = await self.__get_message_text_from_dict(data)
            result: str = text + f"\nОтвет от ИИ: {ai_reply_text}"
            await self.message.answer(result)
            return
        logger.error(f"Davinci NOT ANSWERED to:"
                     f"\n{data}")
        text: str = "ИИ не ответил на реплай:"
        await self.message.answer(text)
        await ErrorsSender.send_report_to_admins(text)
        await self.__send_reply_to_telegram(data)

    @logger.catch
    async def __send_reply_to_telegram(self, data: dict) -> None:
        text: str = await self.__get_message_text_from_dict(data)
        message_id: str = data.get("message_id")
        await self.__reply_to_telegram(text=text, message_id=message_id)

    @logger.catch
    async def __get_message_text_from_dict(self, data) -> str:
        author: str = data.get("author")
        reply_text: str = data.get("text")
        reply_to_author: str = data.get("to_user")
        reply_to_message: str = data.get("to_message")
        return (
            f"Вам пришло сообщение из ДИСКОРДА:"
            f"\nКому: {reply_to_author}"
            f"\nНа сообщение: {reply_to_message}"
            f"\nОт: {author}"
            f"\nText: {reply_text}"
        )

    @logger.catch
    async def __reply_to_telegram(self, text: str, message_id: str) -> None:
        """Отправляет сообщение о реплае в телеграм"""

        answer_keyboard: 'InlineKeyboardMarkup' = InlineKeyboardMarkup(row_width=1)

        answer_keyboard.add(InlineKeyboardButton(
            text="Ответить",
            callback_data=f'reply_{message_id}'
        ))
        await self.message.answer(text, reply_markup=answer_keyboard
        )


    @check_working
    @logger.catch
    async def make_token_pairs(self, unpair: bool = False) -> None:
        """Формирует пары из свободных токенов если они в одном канале"""

        if unpair:
            await DBI.delete_all_pairs(telegram_id=self.__telegram_id)
        await self.form_new_tokens_pairs()

    @logger.catch
    async def form_new_tokens_pairs(self) -> None:
        """Формирует пары токенов из свободных"""

        free_tokens: Tuple[List[namedtuple], ...] = await DBI.get_all_free_tokens(self.__telegram_id)
        formed_pairs: int = 0
        sorted_tokens: Tuple[List[namedtuple], ...] = tuple(
            sorted(
                array, key=lambda x: x.last_message_time, reverse=True
            )
            for array in free_tokens
        )
        self.__related_tokens = []
        for tokens in sorted_tokens:
            while len(tokens) > 1:
                first_token = tokens.pop()
                second_token = tokens.pop()
                formed_pairs += await DBI.make_tokens_pair(first_token.token_pk, second_token.token_pk)
                self.__related_tokens.append(first_token)
                self.__related_tokens.append(second_token)
        if not self.__related_tokens:
            await self.message.answer("Не смог сформировать пары токенов.")
            self.is_working = False
