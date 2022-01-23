import datetime
import os
import sys

from aiogram import Bot, Dispatcher
from dotenv import load_dotenv
from loguru import logger
from peewee import SqliteDatabase
from aiogram.contrib.fsm_storage.memory import MemoryStorage

# Загружаем переменные из файла .env
load_dotenv()

DISCORD_USER_TOKEN = os.getenv("DESKENT_DISCORD")
DESKENT_MEMBER_ID = os.getenv("DESKENT_MEMBER_ID")
PARSING_CHAT_ID = os.getenv("PARSING_CHAT_ID")
USER_LANGUAGE = os.getenv("LANGUAGE")
OPERATOR_CHAT_ID = os.getenv("OPERATOR_CHAT_ID")
LENGTH = 10

deskent = os.getenv("DESKENT_TELEGRAM_ID")
artem = os.getenv("ARTEM_TELEGRAM_ID")
vova = os.getenv("VOVA_TELEGRAM_ID")
# admins_list = [deskent, artem, vova]
admins_list = [deskent]

tgToken = os.getenv("DESKENT_TELEBOT_TOKEN")

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
