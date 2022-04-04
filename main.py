#!/usr/local/bin/python
"""
Python 3.8 or higher
Docker version 20.10.13 +
Redis server v=5.0.14 +
"""

import os.path
import datetime

from aiogram import executor

from admin_handlers import register_admin_handlers
from config import dp, logger, admins_list, bot, db_file_name, VERSION
from handlers import register_handlers
from models import recreate_db

register_admin_handlers(dp=dp)
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
                                         f"\nVersion: {VERSION}"
                                         f"TEST\n")
    except Exception:
        pass
    if not os.path.exists('./db'):
        os.mkdir("./db")
    if not os.path.exists(db_file_name):
        logger.warning(f"Database not found with file name: {db_file_name}")
        recreate_db(db_file_name)

    print('Bot started at:', datetime.datetime.now())
    logger.info("BOT POLLING ONLINE")


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
