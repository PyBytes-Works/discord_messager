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
DEBUG: bool = bool(os.getenv("DEBUG", True))
LOGGING_LEVEL: int = int(os.getenv("LOGGING_LEVEL", 30))

# CONSTANTS
PATH: str = os.getcwd()
TODAY: str = datetime.datetime.today().strftime("%Y-%m-%d")
LOGGING_DIRECTORY: str = os.path.join(PATH, 'logs', TODAY)
ERRORS_LOG: str = 'errors.log'
WARNINGS_LOG: str = 'warnings.log'
ADMINS_LOG: str = 'admins.log'
TOKENS_LOG: str = 'tokens.log'
OPENAI_LOG: str = 'openai.log'

levels: dict = {
    "DEBUG": {
        "config": {"name": "DEBUG", "color": "<white>"},  # "no": 10
        "path": os.path.join(LOGGING_DIRECTORY, ERRORS_LOG)
    },
    "INFO": {
        "config": {"name": "INFO", "color": "<fg #afffff>"},  # "no": 20
        "path": os.path.join(LOGGING_DIRECTORY, ERRORS_LOG)
    },
    "WARNING": {
        "config": {"name": "WARNING", "color": "<light-yellow>"},  # "no": 30
        "path": os.path.join(LOGGING_DIRECTORY, ERRORS_LOG)
    },
    "ERROR": {
        "config": {"name": "ERROR", "color": "<red>"},  # "no": 40
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
    "OPENAI": {
        "config": {"name": "OPENAI", "color": "<yellow>", "no": 80},
        "path": os.path.join(LOGGING_DIRECTORY, OPENAI_LOG)
    },
}
logger.remove()
logger.configure(
    levels=[elem.get("config") for elem in levels.values()]
)
logger.add(sink=levels["ERROR"]["path"], enqueue=True, level='ERROR', rotation="50 MB")
logger.add(sink=levels["WARNING"]["path"], enqueue=True, level='WARNING', rotation="50 MB")
logger.add(
    sink=levels["WARNING"]["path"], enqueue=True, level='WARNING', rotation="50 MB", serialize=True)
logger.add(sink=levels["ADMIN"]["path"], enqueue=True, level='ADMIN', rotation="100 MB")
logger.add(sink=levels["TOKEN"]["path"], enqueue=True, level='TOKEN', rotation="50 MB")
logger.add(sink=levels["OPENAI"]["path"], enqueue=True, level='OPENAI', rotation="50 MB")
logger.add(sink=sys.stdout, level=LOGGING_LEVEL)

logger.info(f'Start logging to: {levels["INFO"]["path"]}')
logger.log('ADMIN', f'Start logging to: {levels["INFO"]["path"]}')
logger.log('TOKEN', f'Start logging to: {levels["INFO"]["path"]}')
logger.log('OPENAI', f'Start logging to: {levels["INFO"]["path"]}')
