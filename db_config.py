import os
from typing import Union

import aioredis
from dotenv import load_dotenv
from peewee import SqliteDatabase, PostgresqlDatabase

from logger_config import logger, PATH

# Загружаем переменные из файла .env
load_dotenv()

# # redis init
REDIS_DB = os.environ.get("REDIS_DB", "redis://127.0.0.1:6379/0")
REDIS_CLIENT = aioredis.from_url(url=REDIS_DB, encoding="utf-8", decode_responses=True)


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
