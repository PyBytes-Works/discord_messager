import aiogram.utils.exceptions

from classes.db_interface import DBI
from config import logger, admins_list, bot
from keyboards import user_menu_keyboard


class ErrorsSender:
    """Отправляет сообщения об ошибках"""

    @classmethod
    async def send_message_check_token(
            cls,
            status: int,
            telegram_id: str,
            admins: bool = False,
            users: bool = True,
            token: str = '',
            proxy: str = '',
            code: int = None,
            *args,
            **kwargs
    ) -> None:
        error_message: str = (
            f"Error status: {status}"
            f"\nTelegram_id: {telegram_id}"
            f"\nToken: {token}"
            f"\nProxy: {proxy}")
        code_message: str = f"\nError code: {code}"
        error_message = error_message + code_message if code else error_message
        logger.error(error_message)
        text: str = ''
        if status == -2:
            text: str = "Ошибка словаря."
            admins = True
        elif status == 400:
            if code == 50035:
                text: str = 'Ошибка токена.'
                admins = False
        elif status == 401:
            if code == 0:
                await DBI.delete_token(token=token)
                text: str = ("Токен сменился и будет удален.\nToken: {token}")
            else:
                text: str = (
                    "Произошла ошибка данных."
                    "\nУбедитесь, что вы ввели верные данные. Код ошибки - 401."
                )
            text = (
                f"Токен "
                f"\n{token} "
                f"\nне прошел проверку в канале. "
                "\nЛибо канал не существует либо токен отсутствует данном канале, либо поменялся."
                "\nТокен удален."
            )
            admins = False
        elif status == 403:
            if code == 50013:
                text: str = (
                    "Не могу отправить сообщение для токена. (Ошибка 403 - 50013)"
                    "Токен в муте."
                    f"\nToken: {token}"
                )
            elif code == 50001:
                await DBI.delete_token(token=token)
                text: str = (
                    "Не могу отправить сообщение для токена. (Ошибка 403 - 50001)"
                    "Токен забанили."
                    f"\nТокен: {token} удален."
                    f"\nФормирую новые пары."
                )
                await DBI.form_new_tokens_pairs(telegram_id=telegram_id)
            else:
                text: str = (f"Ошибка {status}")
        elif status == 404:
            if code == 10003:
                text: str = (
                    "Ошибка отправки сообщения. Неверный канал. (Ошибка 404 - 10003)"
                    f"\nToken: {token}"
                )
            else:
                text: str = (f"Ошибка {status}")
        elif status == 407:
            text = f'Ошибка прокси: {proxy}. Обратитесь к администратору. Код ошибки 407'
            users = True
            admins = True
        elif status == 500:
            text = (
                f"Внутренняя ошибка сервера Дискорда. "
                f"\nПауза 10 секунд. Код ошибки - 500."
            )
        else:
            text = 'Unrecognised error!'
            users = False
            admins = True
        if text:
            if users:
                await cls.errors_report(telegram_id=telegram_id, text=text)
            if admins:
                await cls.send_report_to_admins(text)

    @classmethod
    @logger.catch
    async def errors_report(cls, telegram_id: str, text: str) -> None:
        """Errors report"""

        logger.error(f"Errors report: {text}")
        await bot.send_message(chat_id=telegram_id, text=text, reply_markup=user_menu_keyboard())

    @classmethod
    @logger.catch
    async def send_report_to_admins(cls, text: str) -> None:
        """Отправляет сообщение в телеграме всем администраторам из списка"""

        text = f'[Рассылка][Superusers]: {text}'
        for admin_id in admins_list:
            try:
                await bot.send_message(chat_id=admin_id, text=text, reply_markup=user_menu_keyboard())
            except aiogram.utils.exceptions.ChatNotFound as err:
                logger.error(f"Не смог отправить сообщение пользователю {admin_id}.", err)

    @classmethod
    @logger.catch
    async def proxy_not_found_error(cls):
        text: str = "Нет доступных прокси."
        await cls.send_report_to_admins(text)
