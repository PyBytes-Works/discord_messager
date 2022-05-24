import asyncio
import os

from aiogram import Bot, Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from dotenv import load_dotenv
from logger_config import logger, DEBUG, PATH
from db_config import db, REDIS_CLIENT, DB_FILE_NAME
import psycopg2

# flag for saving files
SAVING: bool = False

# Загружаем переменные из файла .env
load_dotenv()

# Версия приложения
VERSION = os.getenv("VERSION")


# initialization admins list
deskent = os.getenv("DESKENT_TELEGRAM_ID")
artem = os.getenv("ARTEM_TELEGRAM_ID")
vova = os.getenv("VOVA_TELEGRAM_ID")

# set admins list
admins_list = [deskent]
if artem:
    admins_list.append(artem)
if vova:
    admins_list.append(vova)

# Proxy config
PROXY_USER = os.getenv("PROXY_USER")
PROXY_PASSWORD = os.getenv("PROXY_PASSWORD")
DEFAULT_PROXY = os.getenv("DEFAULT_PROXY")
if not DEFAULT_PROXY:
    raise ValueError("Config: DEFAULT_PROXY not found in file .env")

tgToken = os.getenv("TELEBOT_TOKEN")

# configure bot
bot = Bot(token=tgToken)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
SEMAPHORE_MAX_TASKS: int = int(os.getenv("SEMAPHORE_MAX_TASKS"))
SEMAPHORE = asyncio.Semaphore(SEMAPHORE_MAX_TASKS)

# Constants
DISCORD_BASE_URL: str = f'https://discord.com/api/v9/channels/'
