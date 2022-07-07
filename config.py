import asyncio
import os

from aiogram import Bot, Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from pydantic import BaseSettings

from myloguru.mailer import get_mailer_logger


# Constants
DISCORD_BASE_URL: str = f'https://discord.com/api/v9/channels/'
# flag for saving files
SAVING: bool = False


class Settings(BaseSettings):
    STAGE: str
    TELEBOT_TOKEN: str
    PROXY_USER: str
    PROXY_PASSWORD: str
    DEFAULT_PROXY: str
    BASE_API_URL: str
    ADMINS: list = ["305353027"]
    SEMAPHORE_MAX_TASKS: int = 10
    DEBUG: bool = False


settings = Settings(_env_file='.env', _env_file_encoding='utf-8')

# logger
if not os.path.exists('./logs'):
    os.mkdir("./logs")
level = 1 if settings.DEBUG else 30
logger = get_mailer_logger(level)

# set admins list
admins_list = settings.ADMINS

# configure bot
bot = Bot(token=settings.TELEBOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

SEMAPHORE = asyncio.Semaphore(settings.SEMAPHORE_MAX_TASKS)
