#!/usr/local/bin/python
# -*- coding: UTF-8 -*-
"""
Python 3.10 or higher
"""

import os.path
import datetime

from aiogram import executor

from _resources import __appname__, __version__, __build__
from handlers.admin import register_admin_handlers
from config import dp, logger, settings
from handlers.main_handlers import register_handlers
from handlers.login import login_register_handlers
from handlers.token import token_register_handlers
from handlers.cancel_handler import cancel_register_handlers
from classes.errors_reporter import ErrorsReporter
from classes.request_classes import ProxyChecker
from classes.redis_interface import RedisDB

cancel_register_handlers(dp=dp)
login_register_handlers(dp=dp)
register_admin_handlers(dp=dp)
token_register_handlers(dp=dp)
register_handlers(dp=dp)


@logger.catch
async def on_startup(_) -> None:
    """Функция выполняющаяся при старте бота."""

    text: str = (
        f"{__appname__} started:"
        f"\nBuild:[{__build__}]"
        f"\nVersionL[{__version__}]"
    )
    if settings.DEBUG:
        text += "\nDebug: True"
    try:
        await ErrorsReporter.send_report_to_admins(text=text)
    except Exception:
        pass
    if not os.path.exists('./db'):
        os.mkdir("./db")

    user = 'test'
    if await RedisDB(redis_key=user).health_check():
        logger.success("Redis check...OK")
    else:
        logger.warning("Redis check...FAIL")
    proxies: dict = await ProxyChecker().check_all_proxies()
    logger.success(f"Proxies: {proxies}")
    logger.success(
        f'Bot started at: {datetime.datetime.now()}'
        f'\nBOT POLLING ONLINE')


@logger.catch
async def on_shutdown(dp) -> None:
    """Действия при отключении бота."""
    try:
        await ErrorsReporter.send_report_to_admins(text=f"STOPPING: {__appname__} {__version__}")
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
