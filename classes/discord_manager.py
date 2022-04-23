import datetime
import json
import random
from typing import List, Tuple, Optional
from collections import namedtuple

import asyncio

from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove

from classes.message_receiver import MessageReceiver
from classes.message_sender import MessageSender
from classes.token_datastorage import TokenData

from config import logger, DEBUG
from utils import send_report_to_admins
from keyboards import cancel_keyboard, user_menu_keyboard
from classes.db_interface import DBI


class DiscordTokenManager:
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

    @logger.catch
    async def lets_play(self) -> None:
        """Show must go on
        Запускает рабочий цикл бота, проверяет ошибки."""

        self._datastore: 'TokenData' = TokenData(self.user_telegram_id)
        self._datastore.all_tokens_ids = await DBI.get_all_discord_id(telegram_id=self.user_telegram_id)
        await self.__send_text(
            text="Начинаю работу.", keyboard=cancel_keyboard(), check_silence=True)
        while await DBI.is_user_work(telegram_id=self.user_telegram_id):
            if not await self.__prepare_data():
                logger.debug("Not prepared")
                break

            if not await self.__getting_messages():
                logger.debug("Not get messages")
                break

            discord_data: dict = await self.__sending_messages()
            if not discord_data:
                logger.debug("Not discord data")
                break

            await self.__send_replies()

            if not DEBUG:
                timer: float = 7 + random.randint(0, 6)
                logger.info(f"Пауза между отправкой сообщений: {timer}")
                await asyncio.sleep(timer)

            token_work: bool = discord_data.get("work")
            if not token_work:
                text: str = await self.__get_error_text(discord_data=discord_data)
                if text == 'stop':
                    break
                elif text != 'ok':
                    if not self.__silence:
                        await self.message.answer(text, reply_markup=cancel_keyboard())
        logger.debug("Game over.")

    @logger.catch
    async def __prepare_data(self) -> bool:
        logger.debug(f"\tUSER: {self.__username}:{self.user_telegram_id} - Game begin.")
        if await DBI.is_expired_user_deactivated(self.message):
            return False
        return await self.__is_datastore_ready()

    @logger.catch
    async def __getting_messages(self) -> bool:
        message_manager: 'MessageReceiver' = MessageReceiver(datastore=self._datastore)
        await DBI.update_token_last_message_time(token=self._datastore.token)
        datastore: Optional['TokenData'] = await message_manager.get_message()
        if datastore:
            return True
        return False

    @logger.catch
    async def __sending_messages(self) -> dict:
        discord_data: dict = await self.__message_send()
        if not discord_data:
            await send_report_to_admins(
                "Произошла какая то чудовищная ошибка в функции lets_play."
                f"discord_data: {discord_data}\n")
            return {}
        return discord_data

    async def __message_send(self):

        result: dict = {"work": False}
        answer: dict = await MessageSender(datastore=self._datastore).send_message()
        if not answer:
            logger.error("F: Manager.__message_send ERROR: NO ANSWER ERROR")
            result.update({"message": "ERROR"})
            return result
        elif answer.get("status") != 200:
            result.update({"answer": answer, "token": self._datastore.token})
            return result

        self._datastore.current_message_id = 0
        result.update({"work": True})

        return result

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
    async def __is_datastore_ready(self) -> bool:

        if not self.__workers:
            await self.form_token_pairs(unpair=True)
            self.__current_tokens_list: List[namedtuple] = await DBI.get_all_related_user_tokens(
                telegram_id=self._datastore.telegram_id
            )
            if not self.__current_tokens_list:
                await self.__send_text(
                    text="Не смог сформировать пары токенов.", keyboard=user_menu_keyboard())
                return False
            await self.__get_workers()
        if await self.__get_worker_from_list():
            return True
        message: str = await self.__get_all_tokens_busy_message()
        await self.__send_text(text=message, check_silence=True)
        return await self.__sleep()

    @logger.catch
    async def __sleep(self) -> bool:
        logger.info(f"PAUSE: {self._datastore.delay + 1}")
        timer: int = self._datastore.delay + 1
        while timer > 0:
            timer -= 5
            if not await DBI.is_user_work(telegram_id=self.user_telegram_id):
                return False
            await asyncio.sleep(5)
        self._datastore.delay = 0
        return True

    @logger.catch
    async def __get_workers(self) -> None:
        """Возвращает список токенов, которые не на КД"""

        self.__workers = [
            elem.token
            for elem in self.__current_tokens_list
            if
            await self.__get_current_time() > int(elem.last_message_time.timestamp()) + elem.cooldown
        ]

    @logger.catch
    async def __get_worker_from_list(self) -> bool:
        """Возвращает токен для работы"""

        if not self.__workers:
            return False
        random.shuffle(self.__workers)
        random_token: str = self.__workers.pop()
        await self.__update_datastore(random_token)
        return True

    @logger.catch
    async def __get_current_time(self) -> int:
        """Возвращает текущее время (timestamp) целое."""

        return int(datetime.datetime.now().timestamp())

    @logger.catch
    async def __update_datastore(self, token: str) -> None:
        token_data: namedtuple = await DBI.get_info_by_token(token)
        self._datastore.update(token=token, token_data=token_data)

    @logger.catch
    async def __get_all_tokens_busy_message(self) -> str:
        min_token_data: namedtuple = min(self.__current_tokens_list, key=lambda x: x.last_message_time)
        token: str = min_token_data.token
        await self.__update_datastore(token)
        min_token_time: int = int(min_token_data.last_message_time.timestamp())
        delay: int = self._datastore.cooldown - abs(min_token_time - await self.__get_current_time())
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
        return f"Все токены отработали. Следующий старт через {delay} {text}."

    @logger.catch
    async def __send_replies(self) -> None:
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

    @logger.catch
    async def __get_error_text(self, discord_data: dict) -> str:
        """Обработка ошибок от сервера"""

        text: str = discord_data.get("message", "ERROR")
        token: str = discord_data.get("token")
        answer: dict = discord_data.get("answer", {})
        status_code: int = answer.get("status", 0)
        sender_text: str = answer.get("message", "SEND_ERROR")
        data = answer.get("data")
        if isinstance(data, str):
            data: dict = json.loads(answer.get("data", {}))
        discord_code_error: int = data.get("code", 0)

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
                await DBI.delete_token(token=token)
                await self.message.answer("Токен сменился и будет удален."
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
                    f"\nGuild: {self._datastore.guild}"
                    f"\nChannel: {self._datastore.channel}"
                )
            elif discord_code_error == 50001:
                await DBI.delete_token(token=token)
                await self.message.answer(
                    "Не могу отправить сообщение для токена. (Ошибка 403 - 50001)"
                    "Токен забанили."
                    f"\nТокен: {token} удален."
                    f"\nФормирую новые пары.",
                    reply_markup=user_menu_keyboard()
                )
                await self.form_token_pairs(unpair=False)
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
                    cooldown += self._datastore.cooldown
                    await DBI.update_user_channel_cooldown(
                        user_channel_pk=self._datastore.user_channel_pk, cooldown=cooldown)
                    self._datastore.delay = cooldown
                await self.message.answer(
                    "Для данного токена сообщения отправляются чаще, чем разрешено в канале."
                    f"\nToken: {token}"
                    f"\nГильдия/Канал: {self._datastore.guild}/{self._datastore.channel}"
                    f"\nВремя скорректировано. Кулдаун установлен: {cooldown} секунд"
                )
            else:
                await self.message.answer(f"Ошибка: "
                                          f"{status_code}:{discord_code_error}:{sender_text}")
        elif status_code == 500:
            error_text = (
                f"Внутренняя ошибка сервера Дискорда. "
                f"\nГильдия:Канал: {self._datastore.guild}:{self._datastore.channel} "
                f"\nПауза 10 секунд. Код ошибки - 500."
            )
            await self.message.answer(error_text)
            await send_report_to_admins(error_text)
            self._datastore.delay = 10
        else:
            result = text

        return result

    @logger.catch
    async def form_token_pairs(self, unpair: bool = False) -> int:
        """Формирует пары из свободных токенов если они в одном канале"""

        if unpair:
            await DBI.delete_all_pairs(telegram_id=self.user_telegram_id)
        free_tokens: Tuple[
            List[int], ...] = await DBI.get_all_free_tokens(telegram_id=self.user_telegram_id)
        formed_pairs: int = 0
        for tokens in free_tokens:
            while len(tokens) > 1:
                random.shuffle(tokens)
                first_token = tokens.pop()
                second_token = tokens.pop()
                print(first_token, second_token)
                formed_pairs += await DBI.make_tokens_pair(first_token, second_token)

        logger.info(f"Pairs formed: {formed_pairs}")

        return formed_pairs

    @property
    def silence(self) -> bool:
        return self.__silence

    @silence.setter
    def silence(self, silence: bool):
        if not isinstance(silence, bool):
            raise TypeError("Silence must be boolean.")
        self.__silence = silence
