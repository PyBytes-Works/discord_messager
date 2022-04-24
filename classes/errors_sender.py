import aiogram.utils.exceptions

from config import logger, admins_list, bot
from keyboards import user_menu_keyboard


class ErrorsSender:

    @classmethod
    async def send_message(cls, status: int, telegram_id: str):
        pass
        # if status == 407:
        #     answer.update(message='bad proxy')
        # elif status == 401:
        #     answer.update(message='bad token')
        # else:
        #     answer.update(message='check_token failed')
        #
        # return answer

    @classmethod
    @logger.catch
    async def errors_report(cls, telegram_id: str, text: str) -> None:
        """Errors report"""

        logger.error(f"Errors report: {text}")
        await cls.send_report_to_admins(text)
        await bot.send_message(chat_id=telegram_id, text=text, reply_markup=user_menu_keyboard())

    @classmethod
    @logger.catch
    async def send_report_to_admins(cls, text: str) -> None:
        """Отправляет сообщение в телеграме всем администраторам из списка"""

        text = f'[Рассылка][Superusers]: {text}'
        for admin_id in admins_list:
            try:
                await bot.send_message(chat_id=admin_id, text=text)
            except aiogram.utils.exceptions.ChatNotFound as err:
                logger.error(f"Не смог отправить сообщение пользователю {admin_id}.", err)
