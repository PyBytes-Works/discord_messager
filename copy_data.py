import os
import time
from itertools import cycle

from config import PATH, logger, SqliteDatabase
from models import db, User, Token, Proxy, TokenPair, BaseModel


pragmas = dict(db._pragmas)
print(pragmas)
PROXIES = [
            '80.82.222.148:45785',
            '191.101.121.195:45785',
            '195.54.32.125:45785',
            '185.242.85.12:45785',
            '154.16.62.245:45785',
            '51.38.116.219:45785',
            '62.113.216.198:45785',
            '179.61.174.120:45785',
            '213.202.255.50:45785',
            '54.38.154.163:45785'
]

if __name__ == '__main__':
    @logger.catch
    def recreate_db(_db_file_name: str, _db: SqliteDatabase) -> SqliteDatabase:
        """Creates new tables in database. Drop all data from DB if it exists."""
        if os.path.exists(_db_file_name):
            os.remove(_db_file_name)
        _db = SqliteDatabase(_db_file_name, pragmas=pragmas)
        _db.create_tables([BaseModel, User, Token, TokenPair, Proxy], safe=True)

        logger.info('DB REcreated')
        return _db


    source_db_file_name = 'discord_mailer.db'
    source_path = os.path.join(PATH, 'old', source_db_file_name)
    target_db_file_name = 'discord_mailer.db'
    target_path = os.path.join(PATH, target_db_file_name)

    db.close()
    db.database = source_path
    db.connect()
    user_data = [user.__data__ for user in User.select().execute()]
    tokens = [token for token in Token.select().execute()]

    db.close()
    time.sleep(1)
    db.database = target_path
    db = recreate_db(target_path, db)

    for user, proxy in zip(user_data, cycle(PROXIES)):
        user['proxy'] = proxy
        new_user = User.create(**user)
        new_user.save()

    # User.bulk_create(res_users)
    Token.bulk_create(tokens)





    # source_db = SqliteDatabase(source_path, pragmas=pragmas)
    # target_db = recreate_db(target_path)
    # BaseModel.using(source_db)
    #
    # user_data = [user.__data__ for user in User.select().execute()]
    #
    #
    #
    # tokens = [token for token in Token.select().execute()]
    #
    # users = [User(**user) for user in user_data]
    # BaseModel.using(target_db)
    # target_db.create_tables([BaseModel, User, Token, TokenPair, Proxy], safe=True)
    #
    # for user, proxy in zip(user_data, cycle(PROXIES)):
    #     user['proxy'] = proxy
    #     new_user = User.using(target_db).create(**user)
    #     new_user.save()
    #
    # # User.bulk_create(res_users)
    # Token.bulk_create(tokens)

