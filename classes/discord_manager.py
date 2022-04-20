import datetime
import random
from typing import List, Tuple, Optional

import asyncio

from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove

from classes.receiver import MessageReceiver
from classes.token_datastorage import TokenDataStore

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
        self.__current_tokens_list: List[dict] = []
        self.__workers: List[str] = []
        self.__datastore: Optional['TokenDataStore'] = None
        self.__all_tokens_ids: List[str] = []

    @logger.catch
    async def lets_play(self) -> None:
        """Show must go on
        Запускает рабочий цикл бота, проверяет ошибки."""

        # TODO переписать метод для пользователя, а не для токена
        self.__all_tokens_ids = await DBI.get_all_discord_id(telegram_id=self.user_telegram_id)

        while await DBI.is_user_work(telegram_id=self.user_telegram_id):
            await self.__send_text(
                text="Начинаю работу.", keyboard=cancel_keyboard(), check_silence=True)
            logger.debug(f"\tUSER: {self.__username}:{self.user_telegram_id} - Game begin.")
            if await DBI.is_expired_user_deactivated(self.message):
                break
            self.__datastore: 'TokenDataStore' = TokenDataStore(self.user_telegram_id)
            self.__datastore.all_tokens_ids = self.__all_tokens_ids
            if not await self.__is_datastore_ready():
                break
            message_manager: 'MessageReceiver' = MessageReceiver(datastore=self.__datastore)
            await DBI.update_token_time(token=self.__datastore.token)
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
    async def __is_datastore_ready(self) -> bool:

        if not self.__workers:
            await self.form_token_pairs(unpair=True)
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

    @logger.catch
    async def __get_tokens_list(self) -> list:
        """Возвращает список всех токенов пользователя."""

        return await DBI.get_all_related_user_tokens(telegram_id=self.__datastore.telegram_id)

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
        token_data: dict = await DBI.get_info_by_token(random_token)

        self.__datastore.create_datastore_data(token=random_token, token_data=token_data)
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
        token_data: dict = await DBI.get_info_by_token(token)
        self.__datastore.create_datastore_data(token=token, token_data=token_data)
        min_token_time: int = await DBI.get_time_by_token(token)
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
                    cooldown += self.__datastore.cooldown + 2
                    await DBI.update_token_cooldown(token=token, cooldown=cooldown)
                    await DBI.update_mate_cooldown(token=token, cooldown=cooldown)
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
    async def form_token_pairs(self, unpair: bool = False) -> int:
        """Формирует пары из свободных токенов если они в одном канале"""

        if unpair:
            await DBI.delete_all_pairs(telegram_id=self.user_telegram_id)
        free_tokens: Tuple[Tuple[str, list]] = await DBI.get_all_free_tokens(telegram_id=self.user_telegram_id)
        formed_pairs: int = 0
        for channel, tokens in free_tokens:
            while len(tokens) > 1:
                random.shuffle(tokens)
                first_token = tokens.pop()
                second_token = tokens.pop()
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
