#!/usr/local/bin/python
# -*- coding: UTF-8 -*-
"""
Python 3.8 or higher
Docker version 20.10.13 +
Redis server v=5.0.14 +
"""

import os.path
import datetime

from aiogram import executor

from handlers.admin import register_admin_handlers
from config import dp, logger, admins_list, bot, DB_FILE_NAME, VERSION
from handlers.main_handlers import register_handlers
from handlers.login import login_register_handlers
from handlers.token import token_register_handlers
from models import recreate_db

login_register_handlers(dp=dp)
register_admin_handlers(dp=dp)
token_register_handlers(dp=dp)
register_handlers(dp=dp)


async def send_report_to_admins(text: str) -> None:
    """Отправляет сообщение в телеграме всем администраторам из списка"""

    for admin_id in admins_list:
        await bot.send_message(chat_id=admin_id, text=text)


@logger.catch
async def on_startup(_) -> None:
    """Функция выполняющаяся при старте бота."""

    try:
        # Отправляет сообщение админам при запуске бота
        await send_report_to_admins(text="Discord_mailer started."
                                         f"\nVersion: {VERSION}")
    except Exception:
        pass
    if not os.path.exists('./db'):
        os.mkdir("./db")
    if not os.path.exists(DB_FILE_NAME):
        logger.warning(f"Database not found with file name: {DB_FILE_NAME}")
        recreate_db(DB_FILE_NAME)

    logger.info(f'Bot started at: {datetime.datetime.now()}'
                f'\nBOT POLLING ONLINE')


@logger.catch
async def on_shutdown(dp) -> None:
    """Действия при отключении бота."""
    try:
        await send_report_to_admins(text="Discord_mailer stopping.")
    except Exception:
        pass
    logger.warning("BOT shutting down.")
    await dp.storage.wait_closed()
    logger.warning("BOT down.")


@logger.catch
def start_bot() -> None:
    """Инициализация и старт бота"""

    executor.start_polling(
        dispatcher=dp,
        skip_updates=True,
        on_startup=on_startup,
        on_shutdown=on_shutdown,
    )


if __name__ == '__main__':
    start_bot()
