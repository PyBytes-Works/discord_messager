#!/usr/local/bin/python
# -*- coding: UTF-8 -*-
"""
Python 3.10 or higher
"""

import datetime

from aiogram import executor

from _resources import __appname__, __version__, __build__
from config import dp, logger, settings
from classes.errors_reporter import ErrorsReporter
from classes.request_classes import ProxyChecker
from classes.redis_interface import RedisDB
from handlers import *

cancel_register_handlers(dp=dp)
login_register_handlers(dp=dp)
register_admin_handlers(dp=dp)
token_register_handlers(dp=dp)
mailer_register_handlers(dp=dp)
grabber_register_handlers(dp=dp)
joiner_register_handlers(dp=dp)
main_register_handlers(dp=dp)


async def _check_redis() -> str:
    user = 'test'
    redis_text = "Redis check... OK"
    if await RedisDB(redis_key=user).health_check():
        logger.success(redis_text)
    else:
        redis_text = "Redis check... FAIL"
        logger.warning(redis_text)

    return redis_text


async def _check_proxies() -> str:
    proxies: dict = await ProxyChecker().update_tested_proxies()
    logger.debug(proxies.items())
    proxies: str = '\n'.join(proxies)
    proxy_text = f"Proxies checked:\n{proxies}\n"

    return proxy_text


@logger.catch
async def on_startup(_) -> None:
    """Функция выполняющаяся при старте бота."""

    text: str = (
        f"{__appname__} started:"
        f"\nBuild: [{__build__}]"
        f"\nVersion: [{__version__}]"
        f"\n1.3"
    )
    if settings.DEBUG:
        text += "\nDebug: True"
    if settings.STAGE != 'local':
        redis_text = await _check_redis()
        proxy_text = await _check_proxies()
        text += f"\n\n{redis_text}\n\n{proxy_text}"

    await ErrorsReporter.send_report_to_admins(text=text)
    logger.success(
        f'Bot started at: {datetime.datetime.now()}'
        f'\nBOT POLLING ONLINE')


@logger.catch
async def on_shutdown(dp) -> None:
    """Действия при отключении бота."""
    try:
        await ErrorsReporter.send_report_to_admins(
            f"STOPPING: {__appname__} {__version__} {__build__}")
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
