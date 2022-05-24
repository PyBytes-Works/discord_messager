import os
import datetime
import sys

from dotenv import load_dotenv
from loguru import logger


# Загружаем переменные из файла .env
load_dotenv()

# DEBUG setting
DEBUG = bool(os.getenv("DEBUG", 0))

LOGGING_DIRECTORY: str = 'logs'
ERRORS_LOG: str = 'errors.log'
WARNINGS_LOG: str = 'warnings.log'
ADMINS_LOG: str = 'admins.log'
PATH: str = os.getcwd()
if not os.path.exists('./logs'):
    os.mkdir("./logs")
today: str = datetime.datetime.today().strftime("%Y-%m-%d")
errors_file_path: str = os.path.join(PATH, LOGGING_DIRECTORY, today, ERRORS_LOG)
warnings_file_path: str = os.path.join(PATH, LOGGING_DIRECTORY, today, WARNINGS_LOG)
admins_file_path: str = os.path.join(PATH, LOGGING_DIRECTORY, today, ADMINS_LOG)
json_file_path: str = os.path.join(PATH, LOGGING_DIRECTORY, today, 'errors.txt')
DEBUG_LEVEL: str = "INFO"
if DEBUG:
    DEBUG_LEVEL: str = "DEBUG"
logger.remove()
logger.configure(
    levels=[
        dict(name="DEBUG", color="<white>"),
        dict(name="INFO", color="<fg #afffff>"),
        dict(name="WARNING", color="<light-yellow>"),
        dict(name="ERROR", color="<red>"),
        dict(name="ADMIN", color="<fg #d787ff>", no=100),
    ]
)
logger.add(sink=errors_file_path, enqueue=True, level='ERROR', rotation="50 MB")
logger.add(sink=warnings_file_path, enqueue=True, level='WARNING', rotation="50 MB")
logger.add(sink=json_file_path, enqueue=True, level='WARNING', rotation="50 MB", serialize=True)
logger.add(sink=admins_file_path, enqueue=True, level='ADMIN', rotation="100 MB")
logger.add(sink=sys.stdout, level=DEBUG_LEVEL)

logger.info(f'Start logging to: {errors_file_path}')
