import os
import datetime
import sys

from dotenv import load_dotenv
from loguru import logger


# Load variables from .env
load_dotenv()

if not os.path.exists('./logs'):
    os.mkdir("./logs")

# DEBUG settings
DEBUG = bool(os.getenv("DEBUG", 0))

# CONSTANTS
PATH: str = os.getcwd()
TODAY: str = datetime.datetime.today().strftime("%Y-%m-%d")
LOGGING_DIRECTORY: str = os.path.join(PATH, 'logs', TODAY)
ERRORS_LOG: str = 'errors.log'
WARNINGS_LOG: str = 'warnings.log'
ADMINS_LOG: str = 'admins.log'
TOKENS_LOG: str = 'tokens.log'


levels: dict = {
    "DEBUG": {
        "config": {"name": "DEBUG", "color": "<white>"},
        "path": os.path.join(LOGGING_DIRECTORY, ERRORS_LOG)
    },
    "INFO": {
        "config": {"name": "INFO", "color": "<fg #afffff>"},
        "path": os.path.join(LOGGING_DIRECTORY, ERRORS_LOG)
    },
    "WARNING": {
        "config": {"name": "WARNING", "color": "<light-yellow>"},
        "path": os.path.join(LOGGING_DIRECTORY, ERRORS_LOG)
    },
    "ERROR": {
        "config": {"name": "ERROR", "color": "<red>"},
        "path": os.path.join(LOGGING_DIRECTORY, ERRORS_LOG)
    },
    "ADMIN": {
        "config": {"name": "ADMIN", "color": "<fg #d787ff>", "no": 100},
        "path": os.path.join(LOGGING_DIRECTORY, ADMINS_LOG)
    },
    "TOKEN": {
        "config": {"name": "TOKEN", "color": "<white>", "no": 90},
        "path": os.path.join(LOGGING_DIRECTORY, TOKENS_LOG)
    },
}
logger.remove()
logger.configure(
    levels=[elem.get("config") for elem in levels.values()]
)
logger.add(sink=levels["ERROR"]["path"], enqueue=True, level='ERROR', rotation="50 MB")
logger.add(sink=levels["WARNING"]["path"], enqueue=True, level='WARNING', rotation="50 MB")
logger.add(sink=levels["WARNING"]["path"], enqueue=True, level='WARNING', rotation="50 MB", serialize=True)
logger.add(sink=levels["ADMIN"]["path"], enqueue=True, level='ADMIN', rotation="100 MB")
logger.add(sink=levels["TOKEN"]["path"], enqueue=True, level='TOKEN', rotation="50 MB")
logger.add(sink=sys.stdout, level="DEBUG" if DEBUG else "INFO")

logger.debug(f'Start logging to: {levels["ERROR"]["path"]}')

logger.log("TOKEN", 'levels["ERROR"]["path"]')
