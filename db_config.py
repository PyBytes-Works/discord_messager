import aioredis
from pydantic import BaseSettings, RedisDsn
from peewee import PostgresqlDatabase


class Database(BaseSettings):
    POSTGRES_DB: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    REDIS_DB: RedisDsn = "redis://127.0.0.1:6379/0"

    def get_db_name(self):
        return f"postgres://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    def get_db_dict(self) -> dict:
        return dict(
            database=self.POSTGRES_DB,
            user=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_HOST,
            port=self.POSTGRES_PORT
        )


db_config = Database(
    _env_file='.env',
    _env_file_encoding='utf-8'
)

# # redis init
REDIS_CLIENT = aioredis.from_url(url=db_config.REDIS_DB, encoding="utf-8", decode_responses=True)


def psql():
    db = PostgresqlDatabase(**db_config.get_db_dict())
    db.connect()
    return db

db: PostgresqlDatabase = psql()
