from typing import List
import datetime
import os

from peewee import (
    CharField, BooleanField, DateTimeField, ForeignKeyField, IntegerField
)
from peewee import Model
from config import logger, db, admins_list, db_file_name

# ______________________move______________________________


# TODO move
def is_int(text: str) -> bool:
    return text.isdecimal()


@logger.catch
def str_to_int(text: str) -> int:
    if is_int(text):
        try:
            return int(text)
        except ValueError as exc:
            logger.error("can't convert string to number", exc)
# ______________________move______________________________


class BaseModel(Model):
    """A base model that will use our Sqlite database."""

    class Meta:
        database = db
        order_by = 'date_at'


class User(BaseModel):
    """
    Model for table users
      methods
        add_new_user
        activate_user
        check_expiration_date
        deactivate_user
        deactivate_expired_users
        delete_user_by_telegram_id
        delete_status_admin
        is_admin
        is_active
        get_active_users
        get_active_users_not_admins
        set_data_subscriber
        set_expiration_dateset_expiration_date
        get_expiration_date
        get_id_inactive_users
        get_working_users
        get_subscribers_list
        # FIXME delete method? get_telegram_id
        get_user_id_by_telegram_id
        get_user_by_telegram_id
        set_user_is_work
        set_user_is_not_work
        set_user_status_admin
    """

    telegram_id = CharField(unique=True, verbose_name="id пользователя в телеграмм")
    nick_name = CharField(max_length=50, verbose_name="Ник")
    first_name = CharField(max_length=50, null=True, verbose_name="Имя")
    last_name = CharField(max_length=50, null=True, verbose_name="Фамилия")
    active = BooleanField(default=True, verbose_name="Активирован")
    is_work = BooleanField(default=False, verbose_name="В работе / Отдыхает")
    admin = BooleanField(default=False, verbose_name="Администраторство")
    max_tokens = IntegerField(default=1, verbose_name="Максимальное количество токенов")
    channel_id = CharField(max_length=250, default="", verbose_name="Канал дискорда")
    created_at = DateTimeField(
        default=datetime.datetime.now(),
        verbose_name='Дата добавления в базу'
    )
    expiration = IntegerField(
        default=datetime.datetime.now().timestamp(),
        verbose_name='Срок истечения подписки'
    )

    class Meta:
        db_table = "users"

    # @classmethod
    # @logger.catch
    # def get_telegram_id(cls: 'User', id: str) -> str:
    #     """
    #     method returning telegram id for user by user id
    #     if the user is not in the database will return None
    #     return: telegram_id: str
    #     """
    #     user = cls.get_or_none(cls.id == id)
    #     return user.telegram_id if user else None

    @classmethod
    @logger.catch
    def get_user_id_by_telegram_id(cls: 'User', telegram_id: str) -> str:
        """
        if the user is in the database it returns the id, otherwise it returns None
        return: id: str
        """
        user = cls.get_or_none(cls.telegram_id == telegram_id)
        return str(user.id) if user else None

    @classmethod
    @logger.catch
    def get_user_by_telegram_id(cls: 'User', telegram_id: str) -> 'User':
        """
        Returns User`s class instance if user with telegram_id in database else None

        if the user is already in the database, returns the user
        otherwise it will return none

        return: User
        """
        return cls.get_or_none(cls.telegram_id == telegram_id)

    @classmethod
    @logger.catch
    def add_new_user(cls: 'User', nick_name: str, telegram_id: str) -> str:
        """
        if the user is already in the database, returns None
        if created user will return user id
        return: str
        """
        user = cls.get_or_none(cls.telegram_id == telegram_id)
        if not user:
            return cls.create(
                nick_name=f'{nick_name}_{telegram_id}', telegram_id=telegram_id
            ).save()

    @classmethod
    @logger.catch
    def delete_user_by_telegram_id(cls: 'User', telegram_id: str) -> None:
        """
        delete user by telegram id
        """
        user = cls.get_or_none(cls.telegram_id == telegram_id)
        if user:
            user.delete_instance()

    @classmethod
    @logger.catch
    def get_active_users(cls: 'User') -> list:
        """
        return list of telegram ids for active users
        return: list
        """
        return [user.telegram_id
                for user in cls.select(cls.telegram_id)
                .where(cls.active == True).execute()]

    @classmethod
    @logger.catch
    def get_id_inactive_users(cls: 'User') -> list:
        """
        return list of telegram ids for NOT active users
        return: list
        """
        return [user.id for user in cls.select(cls.id)
                    .where(cls.active == False).execute()]

    @classmethod
    @logger.catch
    def get_active_users_not_admins(cls: 'User') -> list:
        """
        return list of telegram ids for active users without admins
        return: list
        """
        return [
            user.telegram_id
            for user in cls.select(cls.telegram_id)
                .where(cls.active == True)
                .where(cls.admin == False)
        ]

    @classmethod
    @logger.catch
    def get_all_users(cls: 'User') -> dict:
        """
        returns dict of all users
        return: dict
        """
        return {
            user.telegram_id: (f'{user.nick_name.rsplit("_", maxsplit=1)[0]} | '
                               f'{"Active" if user.active else "Not active"} | '
                               f'{"Work" if user.is_work else "Not work"} | '
                               f'{"Admin" if user.admin else "Not admin"} | ')
            for user in User.select().execute()
        }

    @classmethod
    @logger.catch
    def get_working_users(cls: 'User') -> list:
        """
        return list of telegram ids for active users with active subscription
        return: list
        """
        return [
            user.telegram_id for user in cls.select(
                cls.telegram_id).where(cls.is_work == True).where(cls.active == True).execute()
        ]

    @classmethod
    @logger.catch
    def set_user_is_work(cls: 'User', telegram_id: str) -> bool:
        """
        set subscriber value enabled for user
        return: 1 if good otherwise 0
        """
        return cls.update(is_work=True).where(cls.telegram_id == telegram_id).execute()

    @classmethod
    @logger.catch
    def set_user_is_not_work(cls: 'User', telegram_id: str) -> bool:
        """
        set subscriber value disabled for user
        return: 1 if good otherwise 0
        """
        return cls.update(is_work=False).where(cls.telegram_id == telegram_id).execute()

    @classmethod
    @logger.catch
    def get_subscribers_list(cls: 'User') -> list:
        """ возвращает список пользователей которым должна отправляться рассылка"""
        now = datetime.datetime.now().timestamp()
        return [user.telegram_id
                for user in cls
                    .select(cls.telegram_id)
                    .where(cls.active == True)
                    .where(cls.is_work == True)
                    .where(cls.expiration > now).execute()]

    @classmethod
    @logger.catch
    def deactivate_user(cls: 'User', telegram_id: str) -> bool:
        """
        set active value disabled for user
        return: 1 if good otherwise 0
        """
        return cls.update(active=False).where(cls.telegram_id == telegram_id).execute()

    @classmethod
    @logger.catch
    def deactivate_expired_users(cls: 'User') -> list:
        """
        return list of telegram ids for active users without admins
        return: list
        """
        now = datetime.datetime.now().timestamp()
        return cls.update(active=False).where(cls.expiration < now).execute()

    @classmethod
    @logger.catch
    def activate_user(cls: 'User', telegram_id: str) -> bool:
        """
        set active value disabled for user
        return: 1 if good otherwise 0
        """
        return cls.update(active=True).where(cls.telegram_id == telegram_id).execute()

    @classmethod
    @logger.catch
    def set_user_status_admin(cls: 'User', telegram_id: str) -> bool:
        """
        set admin value enabled for user
        return: 1 if good otherwise 0
        """
        return cls.update(admin=True).where(cls.telegram_id == telegram_id).execute()

    @classmethod
    @logger.catch
    def set_expiration_date(cls: 'User', telegram_id: str, subscription_period: int) -> bool:
        """
        set subscription expiration date for user
        subscription_period:  (int) number of hours for which the subscription is activated
        """
        now = datetime.datetime.now().timestamp()
        period = subscription_period * 60 * 60 + now
        return cls.update(expiration=period).where(cls.telegram_id == telegram_id).execute()

    @classmethod
    @logger.catch
    def set_max_tokens(cls: 'User', telegram_id: str, max_tokens: int) -> bool:
        """
        set max tokens for user
        subscription_period:  int
        """
        return cls.update(max_tokens=max_tokens).where(cls.telegram_id == telegram_id).execute()

    @classmethod
    @logger.catch
    def check_expiration_date(cls: 'User', telegram_id: str) -> bool:
        """
        возвращает статус подписки пользователя,
        True если подписка ещё действует
        False если срок подписки истёк
        # FIXME
        """
        user: User = cls.get_or_none(cls.telegram_id == telegram_id)
        expiration = user.expiration if user else 0
        return expiration > datetime.datetime.now().timestamp() if expiration else False

    @classmethod
    @logger.catch
    def get_expiration_date(cls: 'User', telegram_id: str) -> int:
        """
        возвращает timestamp без миллисекунд в виде целого числа
        """
        user: User = cls.get_or_none(cls.expiration, cls.telegram_id == telegram_id)
        # print(type(result.expiration))
        expiration = user.expiration
        return expiration

    @classmethod
    @logger.catch
    def get_max_tokens(cls: 'User', telegram_id: str) -> int:
        """
        возвращает timestamp без миллисекунд в виде целого числа
        """
        user = cls.get_or_none(cls.max_tokens, cls.telegram_id == telegram_id)
        if user:
            return user.max_tokens

    @classmethod
    @logger.catch
    def delete_status_admin(cls: 'User', telegram_id: str) -> bool:
        """
        set admin value enabled for user
        return: 1 if good otherwise 0
        """
        return cls.update(admin=False).where(cls.telegram_id == telegram_id).execute()

    @classmethod
    @logger.catch
    def is_admin(cls: 'User', telegram_id: str) -> bool:
        """
        checks if the user is an administrator
        return: bool
        """
        user = cls.get_or_none(cls.telegram_id == telegram_id)
        return user.admin if user else False

    @classmethod
    @logger.catch
    def is_active(cls: 'User', telegram_id: str) -> bool:
        """
        checks if the user is active
        return: bool
        """
        user = cls.get_or_none(cls.telegram_id == telegram_id)
        return user.active if user else False


class UserTokenDiscord(BaseModel):
    """
    Model for table discord_users
      methods
      add_token_by_telegram_id
      get_all_user_tokens
      update_token_time
      get_time_by_token
      delete_inactive_tokens
    """
    user = ForeignKeyField(User, on_delete="CASCADE")
    token = CharField(max_length=255, unique=True, verbose_name="Токен пользователя в discord")
    proxy = CharField(
        default='', max_length=15, unique=False, verbose_name="Адрес прокси сервера"
    )
    guild = CharField(
        default='0', max_length=30, unique=False, verbose_name="Гильдия для подключения"
    )
    channel = CharField(
        default='0', max_length=30, unique=False, verbose_name="Канал для подключения"
    )
    last_message_time = IntegerField(
        default=datetime.datetime.now().timestamp() - 60*5,
        verbose_name="Время отправки последнего сообщения"
    )
    cooldown = IntegerField(
        default=60*5, verbose_name="Время отправки последнего сообщения"
    )

    class Meta:
        db_table = "user_token_discord"

    @classmethod
    @logger.catch
    def add_token_by_telegram_id(cls, telegram_id: str, token: str) -> bool:
        """
        add token by telegram id
        FIXME
        """
        user_id = User.get_user_by_telegram_id(telegram_id)
        all_token = cls.get_all_user_tokens(telegram_id)
        if user_id:
            max_tokens = User.get_max_tokens(telegram_id)
            if max_tokens > len(all_token):
                return cls.get_or_create(user=user_id, token=token)[-1]

    @classmethod
    @logger.catch
    def update_token_time(cls, token: str) -> bool:
        """
        set last_time: now datetime last message
        token: (str)
        """
        last_time = datetime.datetime.now().timestamp()
        return cls.update(last_message_time=last_time).where(cls.token == token).execute()

    @classmethod
    @logger.catch
    def update_token_cooldown(cls, token: str, cooldown: int) -> bool:
        """
        set cooldown: update cooldown for token
         token: (str)
         cooldown: (int) seconds
        """
        return cls.update(cooldown=cooldown).where(cls.token == token).execute()

    @classmethod
    @logger.catch
    def update_token_channel(cls, token: str, channel: int) -> bool:
        """
        set last_time: now datetime last message
         token: (str)
         channel: (int) id cannel
        """
        channel = str(channel)
        return cls.update(channel=channel).where(cls.token == token).execute()

    @classmethod
    @logger.catch
    def update_token_guild(cls, token: str, guild: int) -> bool:
        """
        set last_time: now datetime last message
        token: (str)
        guild: (int) id guild
        """
        guild = str(guild)
        return cls.update(guild=guild).where(cls.token == token).execute()

    @classmethod
    @logger.catch
    def update_token_proxy(cls, token: str, proxy: int) -> bool:
        """
        set last_time: now datetime last message
        token: (str)
        proxy: (str) ip address
        """
        return cls.update(proxy=proxy).where(cls.token == token).execute()

    @classmethod
    @logger.catch
    def get_all_user_tokens(cls, telegram_id: str) -> List[dict]:
        """
        Вернуть список всех ТОКЕНОВ пользователя по его telegram_id:
        return: словарь {token:{'time':время_последнего_сообщения, 'cooldown': кулдаун}}
        """
        user_id = User.get_user_by_telegram_id(telegram_id)
        if user_id:
            return [
                {user.token: {'time': user.last_message_time, 'cooldown': user.cooldown}}
                for user in cls.select(
                    cls.token, cls.last_message_time, cls.cooldown
                ).where(cls.user == user_id)
            ]

    @classmethod
    @logger.catch
    def get_time_by_token(cls, token: str) -> int:
        """
        Вернуть timestamp(кд) токена по его "значению":
        """
        data: 'UserTokenDiscord' = cls.get_or_none(cls.last_message_time, cls.token == token)
        last_message_time = data.last_message_time if data else None
        return last_message_time


    @classmethod
    @logger.catch
    def get_info_by_token(cls, token: str) -> dict:
        """
        Вернуть info по токену
        возвращает словарь:
        {'proxy':proxy(str), 'guild':guild(int), 'channel': channel(int),
        'last_message_time': last_message_time(int, timestamp), 'cooldown': cooldown(int, seconds)}
        если токена нет приходит пустой словарь
        guild, channel по умолчанию 0 если не было изменений вернётся 0
        proxy по умолчанию пусто
        cooldown по умолчанию 5 * 60
        """
        result = {}
        data: 'UserTokenDiscord' = cls.get_or_none(cls.token == token)
        result = {'proxy': data.proxy, 'guild': int(data.guild), 'channel': int(data.channel),
                  'last_message_time': data.last_message_time, 'cooldown': data.cooldown}
        return result

    @classmethod
    @logger.catch
    def delete_token(cls, token: str):
        """Удалить токен по его "значению": """
        data = cls.get_or_none(cls.token == token)
        if data:
            return data.delete_instance()

    @classmethod
    @logger.catch
    def delete_inactive_tokens(cls) -> int:
        """
        removes all tokens for inactive users
        return: number of removed tokens
        """
        users = User.get_id_inactive_users()
        return cls.delete().where(cls.user.in_(users)).execute()


@logger.catch
def drop_db() -> None:
    """Deletes all tables in database"""

    with db:
        try:
            db.drop_tables([User, UserTokenDiscord], safe=True)
            logger.info('DB deleted')
        except Exception as err:
            logger.error(f"Ошибка удаления таблиц БД: {err}")


@logger.catch
def recreate_db(_db_file_name: str) -> None:
    """Creates new tables in database. Drop all data from DB if it exists."""

    with db:
        if os.path.exists(_db_file_name):
            drop_db()
        db.create_tables([User, UserTokenDiscord], safe=True)
        logger.info('DB REcreated')


if __name__ == '__main__':
    recreate = 0
    add_test_users = 0
    add_admins = 0
    add_tokens = 1
    import random
    import string
    test_user_list = (
        (f'test{user}', ''.join(random.choices(string.ascii_letters, k=5)))
        for user in range(1, 6)
    )

    if recreate:
        recreate_db(db_file_name)
    if add_admins:
        for admin_id in admins_list:
            nick_name = "Admin"
            User.add_new_user(nick_name=nick_name, telegram_id=admin_id)
            User.set_user_status_admin(telegram_id=admin_id)
            logger.info(f"User {nick_name} with id {admin_id} created as ADMIN.")
