import datetime
import os
import sys

from aiogram import Bot, Dispatcher
from dotenv import load_dotenv
from loguru import logger
from aiogram.contrib.fsm_storage.memory import MemoryStorage


# Загружаем переменные из файла .env
from peewee import SqliteDatabase

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
DEBUG = int(os.getenv("DEBUG"))
if not DEBUG:
    admins_list = [deskent, artem, vova]

DEFAULT_PROXY = os.getenv("DEFAULT_PROXY")
if not DEFAULT_PROXY:
    raise ValueError("Config: DEFAULT_PROXY not found in file .env")
tgToken = os.getenv("TELEBOT_TOKEN")

# configure bot
bot = Bot(token=tgToken)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)


#  ********** LOGGER CONFIG ********************************
PATH = os.getcwd()
today = datetime.datetime.today().strftime("%Y-%m-%d")
file_path = os.path.join(os.path.relpath(PATH, start=None), 'logs', today, 'discord_mailer.log')

LOG_LEVEL = "ERROR"
logger_cfg = {
   "handlers": [
       {
           "sink": sys.stdout,
           "level": "ERROR",
           "format": "<white>{time:HH:mm:ss}</white> - <lr>{level}</lr> | <green>{message}</green>"
       },
       {
           "sink": sys.stdout,
           "level": "INFO",
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
print('Start logging to:', file_path)
#  ********** END OF LOGGER CONFIG *************************

#  ********** DATABASE CONFIG *************************
db_file_name = 'db/discord_mailer.db'
full_path = os.path.join(PATH, db_file_name)
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
