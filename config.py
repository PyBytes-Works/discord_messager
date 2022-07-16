import asyncio
import os

import fake_useragent
from aiogram import Bot, Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from pydantic import BaseSettings

from myloguru.mailer import get_mailer_logger


# Constants
DISCORD_BASE_URL: str = f'https://discord.com/api/v9/channels/'
# flag for saving files
SAVING: bool = False


class Settings(BaseSettings):
    STAGE: str = 'local'
    LOGGING_LEVEL: int = 20
    TELEBOT_TOKEN: str = ''
    PROXY_USER: str = ''
    PROXY_PASSWORD: str = ''
    DEFAULT_PROXY: str = ''
    BASE_API_URL: str = ''
    PROXY_TEST_URL: str = ''
    ADMINS: list[str] = ["305353027"]
    PROXIES: list[str] = None
    SEMAPHORE_MAX_TASKS: int = 10
    DEBUG: bool = False


settings = Settings(_env_file='.env', _env_file_encoding='utf-8')

# logger
if not os.path.exists('./logs'):
    os.mkdir("./logs")
logger = get_mailer_logger(level=settings.LOGGING_LEVEL)

# set admins list
admins_list = settings.ADMINS[:]

# configure bot
bot = Bot(token=settings.TELEBOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

SEMAPHORE = asyncio.Semaphore(settings.SEMAPHORE_MAX_TASKS)
user_agent = fake_useragent.UserAgent(path='./useragent.json', verify_ssl=False)['google chrome']
