import datetime
import os
import sys

from peewee import SqliteDatabase

from aiogram import Bot, Dispatcher
from dotenv import load_dotenv
from loguru import logger
from aiogram.contrib.fsm_storage.memory import MemoryStorage

# Загружаем переменные из файла .env
load_dotenv()

VERSION = os.getenv("VERSION")

# # redis init
REDIS_DB = os.environ.get("REDIS_DB", "redis://127.0.0.1:6379/0")

# initialization admins list1
deskent = os.getenv("DESKENT_TELEGRAM_ID")
artem = os.getenv("ARTEM_TELEGRAM_ID")
vova = os.getenv("VOVA_TELEGRAM_ID")

# set admins list
admins_list = [deskent]
DEBUG = os.getenv("DEBUG")
DEBUG = True if (int(DEBUG) or DEBUG.lower() == "true") else False
if not DEBUG:
    admins_list = [deskent, artem, vova]

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

# Constants
DISCORD_BASE_URL: str = f'https://discord.com/api/v9/channels/'

#  ********** LOGGER CONFIG ********************************
LOGGING_DIRECTORY = 'logs'
LOGGING_FILENAME = 'discord_mailer.log'
PATH = os.getcwd()
if not os.path.exists('./logs'):
    os.mkdir("./logs")
today = datetime.datetime.today().strftime("%Y-%m-%d")
file_path = os.path.join(PATH, LOGGING_DIRECTORY, today, LOGGING_FILENAME)
LOG_LEVEL = "WARNING"
DEBUG_LEVEL = "INFO"
if DEBUG:
    DEBUG_LEVEL = "DEBUG"
logger_cfg = {
    "handlers": [
        {
            "sink": sys.stdout,
            "level": DEBUG_LEVEL,
            "format": "<white>{time:HH:mm:ss}</white> - <yellow>{level}</yellow> | <green>{message}</green>"
        },
        {
            "sink": file_path, "level": LOG_LEVEL,
            "format": "{time:YYYY-MM-DD HH:mm:ss} - {level} | {message}",
            "rotation": "50 MB"
        },
    ]
}
logger.configure(**logger_cfg)
logger.info('Start logging to:', file_path)
#  ********** END OF LOGGER CONFIG *************************

#  ********** DATABASE CONFIG *************************
DB_FILE_NAME = 'db/discord_mailer.db'
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
#  ********** END OF DATABASE CONFIG *************************
