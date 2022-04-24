import datetime
import json
import random
from typing import List, Optional
from collections import namedtuple

import asyncio

from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove

from classes.message_receiver import MessageReceiver
from classes.message_sender import MessageSender
from classes.token_datastorage import TokenData

from config import logger
from classes.errors_sender import ErrorsSender
from keyboards import cancel_keyboard, user_menu_keyboard
from classes.db_interface import DBI


def check_working(func):
    async def wrapper(*args, **kwargs):
        name: str = func.__name__
        logger.debug(f"\t{name} start:")
        if args and hasattr(args[0].__class__, name):
            working: bool = getattr(args[0], "working")
            if working:
                logger.debug(f"\t{name} start: OK")
                return await func(*args, **kwargs)
        logger.debug(f"\t{name} start: ERROR")
        return
    return wrapper


class DiscordManager:
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
        self.__current_tokens_list: List[namedtuple] = []
        self.__workers: List[str] = []
        self._datastore: Optional['TokenData'] = None
        self.working: bool = True
        self._error_text: str = ''
        self._discord_data: dict = {}

    @logger.catch
    async def lets_play(self) -> None:
        """Show must go on
        Запускает рабочий цикл бота, проверяет ошибки."""

        self._datastore: 'TokenData' = TokenData(self.user_telegram_id)
        self._datastore.all_tokens_ids = await DBI.get_all_discord_id(telegram_id=self.user_telegram_id)
        logger.debug(f"\tUSER: {self.__username}: {self.user_telegram_id} - Game begin.")

        while self.working:
            await self._prepare_data()

            await self._getting_messages()

            if self.working:
                timer: float = 7 + random.randint(0, 6)
                logger.info(f"Пауза между отправкой сообщений: {timer}")
                await asyncio.sleep(timer)

            await self._sending_messages()

            await self._send_replies()

            # await self._get_error_text()
            if not self.__silence and self._error_text:
                await self.message.answer(self._error_text, reply_markup=cancel_keyboard())
        logger.debug("Game over.")

    @check_working
    @logger.catch
    async def _prepare_data(self) -> None:
        if await DBI.is_expired_user_deactivated(self.message):
            self.working = False
            return
        await self._is_datastore_ready()

    @check_working
    @logger.catch
    async def _getting_messages(self) -> None:
        """Получает сообщения из чата и обрабатывает их
        Если удачно - перезаписывает кулдаун текущего токена"""

        message_manager: 'MessageReceiver' = MessageReceiver(datastore=self._datastore)
        datastore: Optional['TokenData'] = await message_manager.get_message()
        if not datastore:
            self.working = False
            return
        await DBI.update_token_last_message_time(token=self._datastore.token)

    @check_working
    @logger.catch
    async def _sending_messages(self) -> None:
        """Отправляет сообщение в дискор и сохраняет данные об ошибках в
        словарь атрибута класса"""

        self.working = False
        if await MessageSender(datastore=self._datastore).send_message():
            self._discord_data = {}
            self._datastore.current_message_id = 0
            self.working = True
        # answer: dict = await MessageSender(datastore=self._datastore).send_message()
        # if answer.get("status") == 200:
        #     self._discord_data = {}
        #     self._datastore.current_message_id = 0
        #     self.working = True
        #     return
        # # elif not answer:
        #     logger.error("F: Manager.__message_send ERROR: NO ANSWER ERROR")
        #     self._discord_data = {"message": "ERROR"}
        # elif answer.get("status") != 200:
        #     self._discord_data = {"answer": answer, "token": self._datastore.token}

    @logger.catch
    async def __send_text(self, text: str, keyboard=None, check_silence: bool = False) -> None:
        """Отправляет текст и клавиатуру пользователю если он не в
        тихом режиме."""

        if check_silence and self.__silence:
            return
        if not keyboard:
            await self.message.answer(text)
            return
        await self.message.answer(text, reply_markup=keyboard)

    @check_working
    @logger.catch
    async def _is_datastore_ready(self) -> None:
        if not self.working:
            return
        if not self.__workers:
            await self.form_token_pairs(unpair=True)
            self.__current_tokens_list: List[namedtuple] = await DBI.get_all_related_user_tokens(
                telegram_id=self._datastore.telegram_id
            )
            logger.debug(f"Current token list: {self.__current_tokens_list}")
            if not self.__current_tokens_list:
                await self.__send_text(
                    text="Не смог сформировать пары токенов.", keyboard=user_menu_keyboard())
                self.working = False
                return
            await self.__get_workers()
        if not await self.__get_worker_from_list():
            await self._get_all_tokens_busy_message()

        self.working = await self._sleep()

    @check_working
    @logger.catch
    async def _sleep(self) -> bool:
        logger.info(f"PAUSE: {self._datastore.delay + 1}")
        timer: int = self._datastore.delay + 1
        while timer > 0:
            timer -= 5
            if not self.working:
                return False
            await asyncio.sleep(5)
        self._datastore.delay = 0
        return True

    @logger.catch
    def __get_max_message_time(self, elem: namedtuple) -> int:
        """Возвращает максимальное время фильтрации сообщения. Сообщения с временем меньше
        данного будут отфильтрованы"""

        return int(elem.last_message_time.timestamp()) + elem.cooldown

    @logger.catch
    async def __get_workers(self) -> None:
        """Возвращает список токенов, которые не на КД"""

        self.__workers = [
            elem.token
            for elem in self.__current_tokens_list
            if self.__get_current_time() > self.__get_max_message_time(elem)
        ]

    @logger.catch
    async def __get_worker_from_list(self) -> bool:
        """Возвращает токен для работы"""

        if not self.__workers:
            return False
        random.shuffle(self.__workers)
        random_token: str = self.__workers.pop()
        await self._update_datastore(random_token)
        return True

    @logger.catch
    def __get_current_time(self) -> int:
        """Возвращает текущее время (timestamp) целое."""

        return int(datetime.datetime.now().timestamp())

    @logger.catch
    async def _update_datastore(self, token: str) -> None:
        token_data: namedtuple = await DBI.get_info_by_token(token)
        self._datastore.update(token=token, token_data=token_data)

    @logger.catch
    async def _get_all_tokens_busy_message(self) -> None:
        min_token_data: namedtuple = min(self.__current_tokens_list, key=lambda x: x.last_message_time)
        token: str = min_token_data.token
        await self._update_datastore(token)
        min_token_time: int = int(min_token_data.last_message_time.timestamp())
        delay: int = self._datastore.cooldown - abs(min_token_time - self.__get_current_time())
        self._datastore.delay = delay
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
        message: str =  f"Все токены отработали. Следующий старт через {delay} {text}."
        await self.__send_text(text=message, check_silence=True)

    @check_working
    @logger.catch
    async def _send_replies(self) -> None:
        """Отправляет реплаи из дискорда в телеграм с кнопкой Ответить"""

        logger.debug(f"Replies: {self._datastore.replies}")
        for reply in self._datastore.replies:
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
    #
    # @check_working
    # @logger.catch
    # async def _get_error_text(self) -> None:
    #     """Обработка ошибок от сервера"""
    #
    #     if not self._discord_data:
    #         return
    #     self._error_text: str = self._discord_data.get("message", "")
    #     token: str = self._discord_data.get("token")
    #     answer: dict = self._discord_data.get("answer", {})
    #     status_code: int = answer.get("status", 0)
    #     sender_text: str = answer.get("message", "SEND_ERROR")
    #     data = answer.get("data")
    #     if isinstance(data, str):
    #         data: dict = json.loads(answer.get("data", {}))
    #     discord_code_error: int = data.get("code", 0)
    #
    #     if status_code == -1:
    #         error_text = sender_text
    #         await self.message.answer("Ошибка десериализации отправки ответа.")
    #         await ErrorsSender.send_report_to_admins(error_text)
    #         self.working = False
    #     elif status_code == -2:
    #         await self.message.answer("Ошибка словаря.", reply_markup=user_menu_keyboard())
    #         await ErrorsSender.send_report_to_admins("Ошибка словаря.")
    #         self.working = False
    #     elif status_code == 400:
    #         if discord_code_error == 50035:
    #             sender_text = 'Сообщение для ответа удалено из дискорд канала.'
    #         else:
    #             self.working = False
    #         await ErrorsSender.send_report_to_admins(sender_text)
    #     elif status_code == 401:
    #         if discord_code_error == 0:
    #             await DBI.delete_token(token=token)
    #             await self.message.answer("Токен сменился и будет удален."
    #                                       f"\nToken: {token}")
    #         else:
    #             await self.message.answer(
    #                 "Произошла ошибка данных. "
    #                 "Убедитесь, что вы ввели верные данные. Код ошибки - 401.",
    #                 reply_markup=user_menu_keyboard()
    #             )
    #         self.working = False
    #     elif status_code == 403:
    #         if discord_code_error == 50013:
    #             await self.message.answer(
    #                 "Не могу отправить сообщение для токена. (Ошибка 403 - 50013)"
    #                 "Токен в муте."
    #                 f"\nToken: {token}"
    #                 f"\nGuild: {self._datastore.guild}"
    #                 f"\nChannel: {self._datastore.channel}"
    #             )
    #         elif discord_code_error == 50001:
    #             await DBI.delete_token(token=token)
    #             await self.message.answer(
    #                 "Не могу отправить сообщение для токена. (Ошибка 403 - 50001)"
    #                 "Токен забанили."
    #                 f"\nТокен: {token} удален."
    #                 f"\nФормирую новые пары.",
    #                 reply_markup=user_menu_keyboard()
    #             )
    #             await self.form_token_pairs(unpair=False)
    #         else:
    #             await self.message.answer(f"Ошибка {status_code}: {data}")
    #     elif status_code == 404:
    #         if discord_code_error == 10003:
    #             await self.message.answer(
    #                 "Ошибка отправки сообщения. Неверный канал. (Ошибка 404 - 10003)"
    #                 f"\nToken: {token}"
    #             )
    #         else:
    #             await self.message.answer(f"Ошибка {status_code}: {data}")
    #     elif status_code == 407:
    #         await self.message.answer(
    #             "Ошибка прокси. Обратитесь к администратору. Код ошибки 407.",
    #             reply_markup=ReplyKeyboardRemove()
    #         )
    #         await ErrorsSender.send_report_to_admins(f"Ошибка прокси. Время действия proxy истекло.")
    #         self.working = False
    #     elif status_code == 429:
    #         if discord_code_error == 20016:
    #             cooldown: int = int(data.get("retry_after", None))
    #             if cooldown:
    #                 cooldown += self._datastore.cooldown
    #                 await DBI.update_user_channel_cooldown(
    #                     user_channel_pk=self._datastore.user_channel_pk, cooldown=cooldown)
    #                 self._datastore.delay = cooldown
    #             await self.message.answer(
    #                 "Для данного токена сообщения отправляются чаще, чем разрешено в канале."
    #                 f"\nToken: {token}"
    #                 f"\nГильдия/Канал: {self._datastore.guild}/{self._datastore.channel}"
    #                 f"\nВремя скорректировано. Кулдаун установлен: {cooldown} секунд"
    #             )
    #         else:
    #             await self.message.answer(f"Ошибка: "
    #                                       f"{status_code}:{discord_code_error}:{sender_text}")
    #     elif status_code == 500:
    #         error_text = (
    #             f"Внутренняя ошибка сервера Дискорда. "
    #             f"\nГильдия:Канал: {self._datastore.guild}:{self._datastore.channel} "
    #             f"\nПауза 10 секунд. Код ошибки - 500."
    #         )
    #         await self.message.answer(error_text)
    #         await ErrorsSender.send_report_to_admins(error_text)
    #         self._datastore.delay = 10

    @logger.catch
    async def form_token_pairs(self, unpair: bool = False) -> None:
        """Формирует пары из свободных токенов если они в одном канале"""

        if unpair:
            await DBI.delete_all_pairs(telegram_id=self.user_telegram_id)
        await DBI.form_new_tokens_pairs(telegram_id=self.user_telegram_id)

    @property
    def silence(self) -> bool:
        return self.__silence

    @silence.setter
    def silence(self, silence: bool):
        if not isinstance(silence, bool):
            raise TypeError("Silence must be boolean.")
        self.__silence = silence
