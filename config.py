import asyncio
import datetime
import os
import sys
from typing import Union

import aioredis
from aiogram import Bot, Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from dotenv import load_dotenv
from loguru import logger
from peewee import SqliteDatabase, PostgresqlDatabase
import psycopg2

# flag for saving files
SAVING: bool = False


# Загружаем переменные из файла .env
load_dotenv()

# Версия приложения
VERSION = os.getenv("VERSION")

# DEBUG setting
DEBUG = bool(os.getenv("DEBUG", 0))

# # redis init
REDIS_DB = os.environ.get("REDIS_DB", "redis://127.0.0.1:6379/0")
REDIS_CLIENT = aioredis.from_url(url=REDIS_DB, encoding="utf-8", decode_responses=True)

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

#  ********** LOGGER CONFIG ********************************
LOGGING_DIRECTORY = 'logs'
ERRORS_FILENAME = 'errors.log'
WARNINGS_FILENAME = 'warnings.log'
PATH = os.getcwd()
if not os.path.exists('./logs'):
    os.mkdir("./logs")
today = datetime.datetime.today().strftime("%Y-%m-%d")
errors_file_path = os.path.join(PATH, LOGGING_DIRECTORY, today, ERRORS_FILENAME)
warnings_file_path = os.path.join(PATH, LOGGING_DIRECTORY, today, WARNINGS_FILENAME)
json_file_path = os.path.join(PATH, LOGGING_DIRECTORY, today, 'errors.txt')
DEBUG_LEVEL = "INFO"
if DEBUG:
    DEBUG_LEVEL = "DEBUG"
logger.remove()
logger.add(sink=errors_file_path, enqueue=True, level='ERROR', rotation="50 MB")
logger.add(sink=warnings_file_path, enqueue=True, level='WARNING', rotation="50 MB")
logger.add(sink=json_file_path, enqueue=True, level='WARNING', rotation="50 MB", serialize=True)
logger.add(sink=sys.stdout, level=DEBUG_LEVEL)
logger.configure(
    levels=[
        dict(name="DEBUG", color="<white>"),
        dict(name="INFO", color="<fg #afffff>"),
        dict(name="WARNING", color="<light-yellow>"),
        dict(name="ERROR", color="<red>"),
    ]
)
logger.info(f'Start logging to: {errors_file_path}')
#  ********** END OF LOGGER CONFIG *************************

#  ********** DATABASE CONFIG *************************


@logger.catch
def psql():
    POSTGRES_DB = os.getenv('POSTGRES_DB')
    POSTGRES_USER = os.getenv('POSTGRES_USER')
    POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD')
    POSTGRES_HOST = os.getenv('POSTGRES_HOST')
    POSTGRES_PORT = os.getenv('POSTGRES_PORT')
    db = PostgresqlDatabase(
        database=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
    )
    db.connect()
    return db


DB_FILE_NAME = 'db/discord_mailer.db'
def sqlite():
    full_path = os.path.join(PATH, DB_FILE_NAME)
    db = SqliteDatabase(
        full_path,
        pragmas={
            'journal_mode': 'wal',
            'cache_size': -1 * 64000,
            'foreign_keys': 0,
            'ignore_check_constraints': 0,
            'synchronous': 0
        }
    )
    return db


DATABASE: str = os.getenv("DATABASE", 'lite')
if DATABASE == 'postgres':
    db: Union[PostgresqlDatabase, SqliteDatabase] = psql()
elif DATABASE == 'lite':
    db: Union[PostgresqlDatabase, SqliteDatabase] = sqlite()

#  ********** END OF DATABASE CONFIG *************************

