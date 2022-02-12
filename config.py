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

# initialization admins list
deskent = os.getenv("DESKENT_TELEGRAM_ID")
artem = os.getenv("ARTEM_TELEGRAM_ID")
vova = os.getenv("VOVA_TELEGRAM_ID")
# admins_list = [deskent, artem, vova]
admins_list = [deskent, vova]

DEFAULT_PROXY = os.getenv("DEFAULT_PROXY")


tgToken = os.getenv("ARTEM_FIRST_BOT_TOKEN")

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
           "level": "INFO",
           "format": "{time:YYYY-MM-DD HH:mm:ss} - {level}: || {message} ||"
       },
       {
            "sink": file_path, "level": LOG_LEVEL,
            "format": "{time:YYYY-MM-DD HH:mm:ss} - {level}: || {message} ||",
            "rotation": "50 MB"
       },
    ]
}
logger.configure(**logger_cfg)
print('Start logging to:', file_path)

#  ********** END OF LOGGER CONFIG *************************



#  ********** DATABASE CONFIG *************************

db_file_name = 'discord_mailer.db'
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
