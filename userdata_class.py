import datetime
import random
from typing import List, Tuple

from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
import asyncio

from config import logger
from discord_handler import MessageReceiver, TokenDataStore
from data_classes import users_data_storage
from models import User, Token
from utils import send_report_to_admins
from keyboards import cancel_keyboard, user_menu_keyboard


class UserData:

    def __init__(self, message: Message) -> None:
        self.message: Message = message
        self.user_telegram_id: str = str(self.message.from_user.id)
        self.deactivate_user_if_expired()

    @logger.catch
    async def lets_play(self):
        """Show must go on
        Запускает рабочий цикл бота, проверяет ошибки."""

        while User.get_is_work(telegram_id=self.user_telegram_id):
            if await self.deactivate_user_if_expired():
                break
            datastore: 'TokenDataStore' = TokenDataStore(self.user_telegram_id)
            users_data_storage.add_or_update(telegram_id=self.user_telegram_id, data=datastore)
            # TODO Реализовать данную функцию в моделях (возвращает True или False) в зависимости от настроек пользователя.
            datastore.silence = False  # User.get_silence()
            message_manager: 'MessageReceiver' = MessageReceiver(datastore=datastore)

            discord_data: dict = await message_manager.get_message()
            if not discord_data:
                await send_report_to_admins("Произошла какая то чудовищная ошибка в функции lets_play.")
                break
            token_work: bool = discord_data.get("work")

            replies: List[dict] = discord_data.get("replies", [])
            if replies:
                await self.send_replies(message=self.message, replies=replies)
            if not token_work:
                text: str = await self.get_error_text(
                    message=self.message, datastore=datastore, discord_data=discord_data
                )
                if text == 'stop':
                    break
                elif text != 'ok':
                    if not datastore.silence:
                        await self.message.answer(text, reply_markup=cancel_keyboard())
                logger.info(f"PAUSE: {datastore.delay + 1}")
                if not datetime.datetime.now().minute % 10:
                    self.form_token_pairs(telegram_id=self.user_telegram_id, unpair=True)
                    logger.info(f"Время распределять токены!")

                await asyncio.sleep(datastore.delay + 1)
                datastore.delay = 0
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
            pairs_formed: int = self.form_token_pairs(telegram_id=self.user_telegram_id, unpair=False)
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
                    "Произошла ошибка данных. Убедитесь, что вы ввели верные данные. Код ошибки - 401.",
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
                self.form_token_pairs(telegram_id=self.user_telegram_id, unpair=False)
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
                await self.message.answer(f"Ошибка: {status_code}:{discord_code_error}:{sender_text}")
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
    async def deactivate_user_if_expired(self) -> bool:
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
