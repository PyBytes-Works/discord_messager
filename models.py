from collections import namedtuple
from itertools import groupby
from typing import List, Tuple, Any, Union, Dict
import datetime
import os

from peewee import (
    Model, CharField, BooleanField, DateTimeField, ForeignKeyField, IntegerField, TimestampField,
    JOIN, Case, fn, BigIntegerField
)

from config import logger, admins_list, db, DB_FILE_NAME, DEFAULT_PROXY


class BaseModel(Model):
    """A base model that will use our Sqlite database."""

    class Meta:
        database = db
        order_by = 'date_at'


class Proxy(BaseModel):
    """
    class for a table proxies
        Methods:
            add_proxy
            delete_proxy
            get_list_proxies
            get_low_used_proxy
            get_proxy_count
            set_proxy_if_not_exists
        fields:
            proxy: str
            using: int ????
    """

    proxy = CharField(max_length=100, unique=True, verbose_name='Адрес прокси с портом.')
    using = IntegerField(default=0, verbose_name='Количество пользователей.')

    @classmethod
    @logger.catch
    def add_proxy(cls, proxy: str) -> bool:
        res = cls.get_or_none(proxy=proxy)
        return False if res else cls.create(proxy=proxy).save()

    @classmethod
    @logger.catch
    def get_proxy_count(cls) -> int:
        return cls.select().count()

    @classmethod
    @logger.catch
    def delete_proxy(cls, proxy: str) -> bool:
        """Proxy removal"""
        return bool(cls.delete().where(cls.proxy == proxy).execute())

    @classmethod
    @logger.catch
    def delete_all_proxy(cls) -> bool:
        """Deletes all proxies, returns deleted proxies count"""

        return cls.delete().execute()

    @classmethod
    @logger.catch
    def get_list_proxies(cls: 'Proxy') -> tuple:
        """return Tuple[Tuple[str, int]] or () """
        result = cls.get()
        return [(inst.proxy, inst.using) for inst in result] if result else ()

    @classmethod
    @logger.catch
    def get_low_used_proxy(cls: 'Proxy') -> namedtuple:
        """
        Возвращает первую прокси с самым малым использованием
        return:
        namedtuple fields:
            proxy_pk: int
            proxy: str
        """
        proxy = (Proxy.select(Proxy.id.alias('proxy_pk'), Proxy.proxy.alias('proxy'), )
                 .join(User, JOIN.LEFT_OUTER, on=(Proxy.id == User.proxy))
                 .group_by(Proxy.id, Proxy.proxy).order_by(fn.COUNT(User.id))
                 .limit(1).namedtuples().first())
        return (
            proxy
            if proxy
            else
            namedtuple('Row', ['proxy_pk', 'proxy'])(proxy_pk=None, proxy=None)
        )

    @classmethod
    @logger.catch
    def set_proxy_if_not_exists(cls: 'Proxy') -> int:
        """
        Метод устанавливает прокси для всех пользователей без прокси
        """
        users = User.select().where(User.proxy.is_null(True)).execute()
        count = 0
        for user in users:
            new_proxy = cls.get_low_used_proxy()
            count += 1
            User.set_proxy_by_telegram_id(telegram_id=user.telegram_id, proxy_pk=new_proxy.proxy_pk)
        return count


class Channel(BaseModel):
    """The Channel class have fields guild_id and channel_id"""
    guild_id = BigIntegerField(verbose_name="Гильдия для подключения")
    channel_id = BigIntegerField(unique=True, verbose_name="Канал для подключения")

    class Meta:
        table_name = 'channel'

    @classmethod
    @logger.catch
    def get_or_create_channel(cls: 'Channel', guild_id: Any, channel_id: Any) -> 'Channel':
        channel, created = cls.get_or_create(guild_id=guild_id, channel_id=channel_id)
        return channel


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
        delete_all_tokens
        is_admin
        is_active
        get_active_users
        get_active_users_not_admins
        get_expiration_date
        get_proxy
        get_id_inactive_users
        get_working_users
        get_subscribers_list
        get_user_id_by_telegram_id
        get_user_by_telegram_id
        set_data_subscriber
        set_expiration_date
        set_user_is_work
        set_user_is_not_work
        set_proxy_by_telegram_id
        set_user_status_admin
    """

    telegram_id = CharField(unique=True, verbose_name="id пользователя в телеграмм")
    nick_name = CharField(max_length=50, verbose_name="Ник")
    first_name = CharField(max_length=50, null=True, verbose_name="Имя")
    last_name = CharField(max_length=50, null=True, verbose_name="Фамилия")
    active = BooleanField(default=True, verbose_name="Активирован")
    is_work = BooleanField(default=False, verbose_name="В работе / Отдыхает")
    admin = BooleanField(default=False, verbose_name="Администраторство")
    max_tokens = IntegerField(default=5, verbose_name="Максимальное количество токенов")
    created_at = DateTimeField(
        default=datetime.datetime.now(),
        verbose_name='Дата добавления в базу'
    )
    expiration = DateTimeField(
        default=datetime.datetime.now(),
        verbose_name='Срок истечения подписки'
    )
    proxy = ForeignKeyField(
        Proxy, backref='user', default=None, null=True,
        verbose_name="Прокси", on_delete='SET NULL')

    class Meta:
        db_table = "users"

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
    def add_new_user(
            cls: 'User',
            nick_name: str,
            telegram_id: str,
            proxy_pk: int,
            expiration: int = 24,
            max_tokens: int = 2
    ) -> 'User':
        """
        if the user is already in the database, returns None
        if created user will return user id
        nick_name: str
        telegram_id: str
        proxy_pk: int
        expiration: int  (hours)
        max_tokens: int

        return: str
        """
        user = cls.select().where(cls.telegram_id == telegram_id).count()
        if not user:
            new_expiration: int = 10 * 365 * 24 if expiration == -1 else expiration
            expiration_time_stamp: float = (
                    datetime.datetime.now().timestamp() + new_expiration * 60 * 60)
            expiration: 'datetime' = datetime.datetime.fromtimestamp(expiration_time_stamp)
            result, answer = cls.get_or_create(
                nick_name=f'{nick_name}_{telegram_id}',
                telegram_id=telegram_id,
                proxy=proxy_pk,
                expiration=expiration,
                max_tokens=max_tokens
            )

            return answer

    @classmethod
    @logger.catch
    def delete_user_by_telegram_id(cls: 'User', telegram_id: str) -> bool:
        """
        delete user by telegram id
        #
        """
        return cls.delete().where(cls.telegram_id == telegram_id).execute()

    @classmethod
    @logger.catch
    def delete_channels(cls: 'User', telegram_id: str) -> int:
        """
        Function removes  user channels and tokens
        """
        return UserChannel.delete().where(
            UserChannel.user.in_(
                cls.select(User.id).where(cls.telegram_id == telegram_id)
            )
        ).execute()

    @classmethod
    @logger.catch
    def delete_all_pairs(cls: 'User', telegram_id: str) -> bool:
        """
        remove all associations of user token pairs and User channels
        """
        # TODO упростить ????
        return TokenPair.delete().where(
            (TokenPair.first_id.in_(
                Token.select(Token.id)
                    .join(UserChannel, JOIN.LEFT_OUTER, on=(Token.user_channel == UserChannel.id))
                    .join(User, JOIN.LEFT_OUTER, on=(UserChannel.user == User.id))
                    .where(User.telegram_id == telegram_id)))
            |
            (TokenPair.second_id.in_(
                Token.select(Token.id)
                    .join(UserChannel, JOIN.LEFT_OUTER, on=(Token.user_channel == UserChannel.id))
                    .join(User, JOIN.LEFT_OUTER, on=(UserChannel.user == User.id))
                    .where(User.telegram_id == telegram_id)))
        ).execute()

    @classmethod
    @logger.catch
    def get_active_users(cls: 'User') -> List[str]:
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
    def get_all_inactive_users(cls: 'User') -> Dict[str, 'User']:
        """
        return dict of NOT active users
        return: dict
        """
        return {
            user.telegram_id: user
            for user in cls.select().where(cls.active == False).execute()
        }

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
    def get_all_users(cls: 'User') -> Tuple[namedtuple]:
        """
        returns dict of all users
        return: named tuple
        list of namedtuple fields:
            nick_name: str
            active: str
            admin: str
            proxy: str
            telegram_id: str
            max_tokens: int
            expiration: timestamp
        """
        return tuple(User.select(
            User.nick_name.alias('nick_name'),
            User.active.alias('active'),
            User.admin.alias('admin'),
            Proxy.proxy.alias('proxy'),
            User.telegram_id.alias('telegram_id'),
            User.max_tokens.alias('max_tokens'),
            User.expiration.alias('expiration'),
        ).join(Proxy, JOIN.LEFT_OUTER, on=(
                    User.proxy == Proxy.id)).order_by(User.created_at).namedtuples().execute())

    @classmethod
    @logger.catch
    def get_is_work(cls: 'User', telegram_id: str) -> bool:
        """
        return list of telegram ids for active users with active subscription
        return: list
        """
        user = User.get_or_none(telegram_id=telegram_id)
        if user:
            return user.is_work

    @classmethod
    @logger.catch
    def get_working_users(cls: 'User') -> List[str]:
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
        """ Возвращает список пользователей которым должна отправляться рассылка"""
        now = datetime.datetime.now()
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
        cls.delete_channels(telegram_id=telegram_id)
        return cls.update(active=False).where(cls.telegram_id == telegram_id).execute()

    @classmethod
    @logger.catch
    def deactivate_expired_users(cls: 'User') -> list:
        """
        return list of telegram ids for active users without admins
        return: list
        """
        now = datetime.datetime.now()
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
    def delete_proxy_for_all_users(cls: 'User') -> int:
        """Delete all user proxies, returns deleted proxies count"""

        return cls.update(proxy=None).execute()

    @classmethod
    @logger.catch
    def set_new_proxy_for_all_users(cls: 'User') -> int:
        """Set up proxies for all users"""

        all_users: List['User'] = list(cls.select().execute())
        for user in all_users:
            proxy: namedtuple = Proxy.get_low_used_proxy()
            if not proxy.proxy_pk:
                return 0
            cls.set_proxy_by_telegram_id(telegram_id=str(user.telegram_id), proxy_pk=proxy.proxy_pk)
        return len(all_users)

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
        new_period = datetime.datetime.fromtimestamp(period)
        return cls.update(expiration=new_period).where(cls.telegram_id == telegram_id).execute()

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
    def set_proxy_by_telegram_id(cls: 'User', telegram_id: str, proxy_pk: int) -> bool:
        """
        set proxy for user
        telegram_id:  str
        proxy_pk:  int
        """
        return cls.update(proxy=proxy_pk).where(cls.telegram_id == telegram_id).execute()

    @classmethod
    @logger.catch
    def is_subscribe_active(cls: 'User', telegram_id: str) -> bool:
        """
        Возвращает статус подписки пользователя,

        False если срок подписки истёк

        True если подписка действует
        """

        user: User = cls.get_or_none(cls.telegram_id == telegram_id)
        expiration = user.expiration if user else datetime.datetime.now()

        return expiration > datetime.datetime.now() if expiration else False

    @classmethod
    @logger.catch
    def get_expiration_date(cls: 'User', telegram_id: str) -> int:
        """
        Возвращает timestamp без миллисекунд в виде целого числа
        """
        user = cls.get_or_none(cls.telegram_id == telegram_id)
        if user:
            expiration = user.expiration

            return expiration

    @classmethod
    @logger.catch
    def get_proxy(cls: 'User', telegram_id: str) -> str:
        """
        Возвращает прокси пользователя
        """
        user: User = cls.get_or_none(cls.telegram_id == telegram_id)
        if user and user.proxy:
            return str(user.proxy.proxy)

    @classmethod
    @logger.catch
    def get_max_tokens(cls: 'User', telegram_id: str) -> int:
        """
         Return the maximum number of tokens for a user
        """
        user = cls.get_or_none(cls.telegram_id == telegram_id)
        if user:
            return user.max_tokens
        return 0

    @classmethod
    @logger.catch
    def delete_status_admin(cls: 'User', telegram_id: str) -> bool:
        """
        set admin value disabled for a user
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

    @classmethod
    @logger.catch
    def unwork_all_users(cls):
        """
        set unwork status for all users
        """
        return cls.update(is_work=False).execute()

    @classmethod
    @logger.catch
    def work_all_users(cls):
        """
        set work status enabled fo all users
        """
        now = datetime.datetime.now()
        return cls.update(active=True).where(cls.expiration > now).execute()


class UserChannel(BaseModel):
    """
    class user channel for save user's channels and cooldown
    methods:
        add_user_channel
        get_user_channels
        get_all_user_channel_by_telegram_id
        set_user_channel_name
        update_cooldown_by_channel_id
        delete_user_channel
    """

    user = ForeignKeyField(
        User, backref='user_channel', verbose_name='Пользователь', on_delete='CASCADE')
    name = CharField(default='', max_length='100', verbose_name='Название канала')
    channel = ForeignKeyField(
        Channel, backref='user_channel', verbose_name='Канал', on_delete='CASCADE')
    cooldown = IntegerField(default=60, verbose_name="Задержка между сообщениями")

    class Meta:
        table_name = 'user_channel'
        indexes = ((('user', 'channel'), True),)

    @classmethod
    @logger.catch
    def add_user_channel(
            cls: 'UserChannel',
            telegram_id: str,
            guild_id: int,
            channel_id: int,
            name: str = '',
            cooldown: int = 60) -> int:
        """
        Функция создает запись связи пользователя с дискорд каналом
        если канала нет, он будет создан
        """
        if not name:
            name: str = str(channel_id)
        user = User.get_user_by_telegram_id(telegram_id=telegram_id)
        channel = Channel.get_or_create_channel(guild_id=guild_id, channel_id=channel_id)
        user_channel: UserChannel = (cls.select()
                                     .where(cls.channel == channel.id)
                                     .where(cls.user == user.id)
                                     .first())
        if user_channel:
            user_channel.name = name
            user_channel.save()
        else:
            user_channel, answer = cls.get_or_create(
                user=user,
                name=name,
                channel=channel.id,
                cooldown=cooldown
            )

        return user_channel.id

    @classmethod
    @logger.catch
    def get_user_channels_by_telegram_id(
            cls: 'UserChannel', telegram_id: Union[str, int]) -> List[namedtuple]:
        """
        Function returns a list of named tuples
        list of namedtuple fields:
            user_channel_pk: int
            channel_name: str
            cooldown: int
            channel_id: int
            guild_id: int
        """
        return list(
            cls.select(
                cls.id.alias('user_channel_pk'),
                cls.name.alias('channel_name'),
                cls.name.alias('cooldown'),
                Channel.channel_id.alias('channel_id'),
                Channel.guild_id.alias('guild_id')
            )
                .join(Channel, JOIN.LEFT_OUTER, on=(Channel.id == cls.channel))
                .join(User, JOIN.LEFT_OUTER, on=(User.id == cls.user))
                .where(User.telegram_id == telegram_id).namedtuples().execute()
        )

    @classmethod
    @logger.catch
    def delete_user_channel(cls: 'UserChannel', user_channel_pk: int) -> int:
        """Удаляет пользовательский канал связанные токены удаляются автоматически"""
        return cls.delete().where(cls.id == user_channel_pk).execute()

    @classmethod
    @logger.catch
    def get_user_channel(
            cls: 'UserChannel', user_channel_pk: int) -> namedtuple:
        """
        Function returns a list of named tuples
        list of namedtuple fields:
            user_channel_pk: int
            channel_name: str
            cooldown: int
            channel_id: int
            guild_id: int
        """
        return (
            cls.select(
                cls.id.alias('user_channel_pk'),
                cls.name.alias('channel_name'),
                cls.name.alias('cooldown'),
                Channel.channel_id.alias('channel_id'),
                Channel.guild_id.alias('guild_id')
            )
                .join(Channel, JOIN.LEFT_OUTER, on=(Channel.id == cls.channel))
                .where(cls.id == user_channel_pk).namedtuples().first()
        )

    @classmethod
    @logger.catch
    def set_user_channel_name(cls: 'UserChannel', user_channel_pk: int, name: str) -> int:
        """
        Update name for one users_channel by user_channel_id
        returns the number of updated records
        """
        return cls.update(name=name).where(cls.id == user_channel_pk).execute()

    @classmethod
    @logger.catch
    def update_cooldown(cls: 'UserChannel', user_channel_pk: int, cooldown: int) -> int:
        """
        Update cooldown for all users_channel by channel_id
        """
        return cls.update(cooldown=cooldown).where(cls.id == user_channel_pk).execute()


class Token(BaseModel):
    """
    Model for table discord_users
      methods:
          add_token_by_telegram_id
          is_token_exists
          get_all_user_tokens
          get_all_info_tokens
          get_number_of_free_slots_for_tokens
          get_min_last_time_token_data
          get_time_by_token
          get_token_info
          get_token_info_by_token_pk
          get_all_free_tokens
          get_all_discord_id
          get_all_discord_id_by_channel
          get_count_bu_user_channel
          set_token_name
          check_token_by_discord_id
          update_token_time
    """
    user_channel = ForeignKeyField(
        UserChannel, backref='token', verbose_name="Канал для подключения", on_delete='CASCADE')
    name = CharField(max_length=100, verbose_name="Название токена")
    token = CharField(max_length=255, unique=True, verbose_name="Токен пользователя в discord")
    discord_id = CharField(max_length=255, unique=True, verbose_name="ID пользователя в discord")
    last_message_time = TimestampField(
        default=datetime.datetime.now().timestamp() - 60 * 5,
        verbose_name="Время отправки последнего сообщения"
    )

    class Meta:
        db_table = "tokens"

    @classmethod
    @logger.catch
    def is_token_exists(cls: 'Token', token: str) -> bool:
        return bool(cls.select().where(cls.token == token).count())

    @classmethod
    @logger.catch
    def get_all_user_tokens(cls: 'Token', telegram_id: str) -> int:
        """Returns TOTAL token user amount"""
        return (
            cls.select()
                .join(UserChannel, JOIN.LEFT_OUTER, on=(UserChannel.id == cls.user_channel))
                .join(User, JOIN.LEFT_OUTER, on=(UserChannel.user == User.id))
                .where(User.telegram_id == telegram_id).count()
        )

    @classmethod
    @logger.catch
    def add_token(
            cls,
            telegram_id: Union[str, int],
            token: str,
            discord_id: str,
            user_channel_pk: int,
            name: str = '',
    ) -> bool:

        """
        Add a new token to the client channel
        return: bool True if write was successful,
        False if this token or discord_id already exists in the database
        or the number of tokens is equal to the limit
        """
        if not name:
            name: str = token
        limit: int = cls.get_number_of_free_slots_for_tokens(telegram_id=telegram_id)
        answer: bool = False
        if limit:
            token, answer = cls.get_or_create(
                user_channel=user_channel_pk,
                name=name,
                token=token,
                discord_id=discord_id,
            )
        return answer

    @classmethod
    @logger.catch
    def update_token_last_message_time(cls, token: str) -> bool:
        """
        set last_time: now datetime last message
        token: (str)
        """
        current_time = datetime.datetime.now().timestamp()
        return cls.update(last_message_time=current_time).where(cls.token == token).execute()

    @classmethod
    @logger.catch
    def make_tokens_pair(cls: 'Token', first: int, second: int) -> bool:
        """
        Make pair
        first_pk: (int)
        second_pk: (int)
            unites tokens in pair
        """
        return bool(TokenPair.add_pair(first=first, second=second))

    @classmethod
    @logger.catch
    def delete_token_pair(cls, token: str) -> bool:
        """
            Удаляет пару по токен
        """
        result = False
        token_data: 'Token' = cls.get_or_none(token=token)
        if token_data:
            result = TokenPair.delete_pair(token_id=token_data.id)
        return bool(result)

    @classmethod
    @logger.catch
    def update_token_info(
            cls, token: str, user_channel: int
    ) -> bool:
        """
        update user_channel by token
        token: (str)
        user_channel: int pk user_channel
        """
        data = cls.get_or_none(token=token)
        if token:
            TokenPair.delete_pair(token_id=data.id)
            return (cls.update(user_channel=user_channel)
                    .where(cls.token == token).execute())

    @classmethod
    @logger.catch
    def get_related_tokens(cls: 'User', telegram_id: Union[str, int] = None) -> List[namedtuple]:
        """
        Вернуть список всех связанных ТОКЕНОВ пользователя по его telegram_id:
        return: list of named tuples
        list of namedtuple fields:
            token str
            cooldown  int
            last_message_time Timestamp
        """
        query = (cls.select(
            cls.token.alias('token'),
            cls.last_message_time.alias('last_message_time'),
            UserChannel.cooldown.alias('cooldown'))
                 .join(UserChannel, JOIN.LEFT_OUTER,
            on=(cls.user_channel == UserChannel.id))
                 .join(Channel, JOIN.LEFT_OUTER, on=(UserChannel.channel == Channel.id))
                 .join(User, JOIN.LEFT_OUTER, on=(UserChannel.user == User.id))
                 .join(TokenPair, JOIN.RIGHT_OUTER,
            on=(TokenPair.first_id == cls.id))
                 .where(User.telegram_id == telegram_id).namedtuples()
                 )
        return [data for data in query]

    @classmethod
    @logger.catch
    def get_all_tokens_info(cls, telegram_id: Union[str, int] = None) -> List[namedtuple]:
        """
        Вернуть список всех ТОКЕНОВ пользователя по его telegram_id:
        return:
        list of namedtuple fields:
            token str
            token_pk int
            token_discord_id str
            proxy str
            user_channel_pk int
            channel_id int
            guild_id int
            cooldown  int
            mate_discord_id str (discord_id)

        """
        data = (cls.select(
            cls.token.alias('token'),
            cls.id.alias('token_pk'),
            cls.discord_id.alias('token_discord_id'),
            Proxy.proxy.alias('proxy'),
            cls.name.alias('token_name'),
            UserChannel.id.alias('user_channel_pk'),
            Channel.channel_id.alias('channel_id'),
            Channel.guild_id.alias('guild_id'),
            UserChannel.cooldown.alias('cooldown'),
            cls.alias('pair').discord_id.alias('mate_discord_id')
        )
                .join(UserChannel, JOIN.LEFT_OUTER,
            on=(cls.user_channel == UserChannel.id))
                .join(Channel, JOIN.LEFT_OUTER, on=(UserChannel.channel == Channel.id))
                .join(User, JOIN.LEFT_OUTER, on=(UserChannel.user == User.id))
                .join(Proxy, JOIN.LEFT_OUTER, on=(Proxy.id == User.proxy))
                .join(TokenPair, JOIN.LEFT_OUTER, on=(cls.id == TokenPair.first_id))
                .join(cls.alias('pair'), JOIN.LEFT_OUTER,
            on=(cls.alias('pair').id == TokenPair.second_id))
                .where(User.telegram_id == telegram_id).namedtuples()
                )
        return list(data)

    @classmethod
    @logger.catch
    def get_all_discord_id(cls, telegram_id: str) -> List[str]:
        """
        Вернуть список всех дискорд ID пользователя по его telegram_id:
        return: (list) список discord_id
        """
        tokens = (cls.select(
            cls.discord_id.alias('discord_id'),
        )
                  .join_from(cls, UserChannel, JOIN.LEFT_OUTER,
            on=(cls.user_channel == UserChannel.id))
                  .join_from(cls, Channel, JOIN.LEFT_OUTER, on=(UserChannel.channel == Channel.id))
                  .join_from(cls, User, JOIN.LEFT_OUTER, on=(UserChannel.user == User.id))
                  .where(User.telegram_id == telegram_id).namedtuples().execute())
        return [data.discord_id for data in tokens] if tokens else []

    @classmethod
    @logger.catch
    def get_all_discord_id_by_channel(cls, user_channel_pk: int) -> List[namedtuple]:
        """
        return: list named tuples

        """
        return list(cls.select(cls.discord_id.alias('discord_id'))
            .where(cls.user_channel == user_channel_pk).namedtuples().execute())

    @classmethod
    @logger.catch
    def get_all_free_tokens(cls, telegram_id: Union[str, int] = None) -> Tuple[
        List[namedtuple], ...]:
        """
        Возвращает список всех свободных токенов по каналам
            token_pk int
            token str
            last_message_time datetime
            cooldown  int
            channel_id int
        """
        data = (
            cls.select(
                cls.id.alias('token_pk'),
                cls.token.alias('token'),
                cls.last_message_time.alias('last_message_time'),
                UserChannel.cooldown.alias('cooldown'),
                Channel.channel_id.alias('channel_id'),
            )
                .join_from(cls, UserChannel, JOIN.LEFT_OUTER, on=(
                    cls.user_channel == UserChannel.id))
                .join_from(cls, Channel, JOIN.LEFT_OUTER, on=(UserChannel.channel == Channel.id))
                .join_from(cls, User, JOIN.LEFT_OUTER, on=(UserChannel.user == User.id))
                .join_from(cls, TokenPair, JOIN.LEFT_OUTER, on=(TokenPair.first_id == cls.id))
                .where(User.telegram_id == telegram_id)
                .where(TokenPair.first_id.is_null(True)).namedtuples().execute()
        )
        result: Tuple[List[int], ...] = tuple(
            [token for token in tokens]
            for channel, tokens in
            groupby(data, lambda x: x.channel_id)
        )
        return result

    @classmethod
    @logger.catch
    def get_last_message_time(cls: 'Token', token: str) -> int:
        """
        Вернуть timestamp(кд) токена по его "значению":
        """
        data = cls.get_or_none(cls.token == token)
        last_message_time = data.last_message_time if data else None
        return last_message_time

    @classmethod
    @logger.catch
    def check_token_by_discord_id(cls, discord_id: str) -> bool:
        """
        Проверка токена по discord_id
        """
        data = cls.select().where(cls.discord_id == discord_id).execute()
        return True if data else False

    @classmethod
    @logger.catch
    def get_token_info(cls: 'Token', token: str) -> namedtuple:
        """
        Вернуть info по токен
        возвращает объект токен
            'user_channel_pk' int
            'proxy':proxy(str),
            'guild_id':guild_id(int),
            'channel_id': channel_id(int),
            'cooldown': cooldown(int, seconds)}
            'mate_discord_id' str (discord_id)
            'token_discord_id' str
            'token_name' str
        """

        data = (
            cls.select(
                cls.user_channel.alias('user_channel_pk'),
                Proxy.proxy.alias('proxy'),
                Channel.guild_id.alias('guild_id'),
                Channel.channel_id.alias('channel_id'),
                UserChannel.cooldown.alias('cooldown'),
                cls.alias('pair').discord_id.alias('mate_discord_id'),
                cls.discord_id.alias('token_discord_id'),
                cls.name.alias('token_name'),
            )
                .join(UserChannel, JOIN.LEFT_OUTER, on=(cls.user_channel == UserChannel.id))
                .join(Channel, JOIN.LEFT_OUTER, on=(UserChannel.channel == Channel.id))
                .join(User, JOIN.LEFT_OUTER, on=(UserChannel.user == User.id))
                .join(TokenPair, JOIN.LEFT_OUTER, on=(TokenPair.first_id == cls.id))
                .join(Proxy, JOIN.LEFT_OUTER, on=(Proxy.id == User.proxy))
                .join(cls.alias('pair'), JOIN.LEFT_OUTER,
                on=(cls.alias('pair').id == TokenPair.second_id))
                .where(cls.token == token).namedtuples().first()
        )

        return data

    @classmethod
    @logger.catch
    def get_token_info_by_token_pk(cls: 'Token', token_pk: int) -> namedtuple:
        """
        Вернуть info по токен
        возвращает namedtuple
        list of namedtuple fields:
            token str
            token_pk int
            token_discord_id str
            proxy str
            user_channel_pk int
            channel_id int
            guild_id int
            cooldown  int
            mate_discord_id str (discord_id)

        """
        data = (cls.select(
            cls.token.alias('token'),
            cls.id.alias('token_pk'),
            cls.discord_id.alias('token_discord_id'),
            Proxy.proxy.alias('proxy'),
            cls.name.alias('token_name'),
            UserChannel.id.alias('user_channel_pk'),
            Channel.channel_id.alias('channel_id'),
            Channel.guild_id.alias('guild_id'),
            UserChannel.cooldown.alias('cooldown'),
            cls.alias('pair').discord_id.alias('mate_discord_id')
        )
                .join(UserChannel, JOIN.LEFT_OUTER, on=(cls.user_channel == UserChannel.id))
                .join(Channel, JOIN.LEFT_OUTER, on=(UserChannel.channel == Channel.id))
                .join(User, JOIN.LEFT_OUTER, on=(UserChannel.user == User.id))
                .join(TokenPair, JOIN.LEFT_OUTER, on=(TokenPair.first_id == cls.id))
                .join(Proxy, JOIN.LEFT_OUTER, on=(Proxy.id == User.proxy))
                .join(cls.alias('pair'), JOIN.LEFT_OUTER,
            on=(cls.alias('pair').id == TokenPair.second_id))
                .where(cls.id == token_pk).namedtuples().first()
                )

        return data

    # @classmethod
    # @logger.catch
    # def get_closest_token_time(cls: 'Token', telegram_id: str) -> namedtuple:
    #     """
    #     Вернуть info по токен
    #     возвращает объект токен
    #         'cooldown': cooldown(int, seconds)}
    #         'last_message_time' int
    #     """
    #     data = (
    #         cls.select(
    #             UserChannel.cooldown.alias('cooldown'),
    #             cls.last_message_time.alias('last_message_time'),
    #         )
    #             .join(UserChannel, JOIN.LEFT_OUTER, on=(cls.user_channel == UserChannel.id))
    #             .join(Channel, JOIN.LEFT_OUTER, on=(UserChannel.channel == Channel.id))
    #             .join(User, JOIN.LEFT_OUTER, on=(UserChannel.user == User.id))
    #             .join(TokenPair, JOIN.LEFT_OUTER, on=(TokenPair.first_id == cls.id))
    #             .join(Proxy, JOIN.LEFT_OUTER, on=(Proxy.id == User.proxy))
    #             .join(cls.alias('pair'), JOIN.LEFT_OUTER,
    #             on=(cls.alias('pair').id == TokenPair.second_id))
    #             .where(User.telegram_id == telegram_id)
    #             .order_by(cls.last_message_time).namedtuples().first()
    #     )

        return data if data else namedtuple(
            'Row', ['cooldown', 'last_message_time'])(cooldown=None, last_message_time=None)

    @classmethod
    @logger.catch
    def get_count_bu_user_channel(cls, user_channel_pk: int) -> int:
        """Get numbers token by channel id"""
        return cls.select().where(cls.user_channel == user_channel_pk).count()

    @classmethod
    @logger.catch
    def delete_token_by_id(cls, token_pk: int) -> int:
        """Deleting token by id"""
        return cls.delete().where(cls.id == token_pk).execute()

    @classmethod
    @logger.catch
    def set_token_name(cls: 'Token', token_pk: int, name: str) -> int:
        """Set new name for token"""
        return cls.update(name=name).where(cls.id == token_pk).execute()

    @classmethod
    @logger.catch
    def delete_token(cls, token: str) -> int:
        """Удалить токен по его "значению": """
        return cls.delete().where(cls.token == token).execute()

    @classmethod
    @logger.catch
    def get_number_of_free_slots_for_tokens(cls, telegram_id: str) -> int:
        """
        Вернуть количество свободных мест для размещения токенов
        TODO admin super admin
        """
        return (
            User.select(
                Case(
                    None,
                    [
                        ((fn.MAX(User.max_tokens).is_null(False)),
                         fn.MAX(User.max_tokens) - fn.COUNT(Token.id),)
                    ],
                    0
                )
                    .alias('limit')
            )
                .join(UserChannel, JOIN.LEFT_OUTER, on=(UserChannel.user == User.id))
                .join(cls, JOIN.LEFT_OUTER, on=(cls.user_channel == UserChannel.id))
                .where(User.telegram_id == telegram_id)
                .namedtuples()
                .first()
                .limit
        )


class TokenPair(BaseModel):
    """
    class for a table of related token pairs
        Methods:
            add_pair
            delete_pair
            remove_all_pairs
            get_token_mate
            get_all_related_tokens
     """

    first_id = ForeignKeyField(
        Token, unique=True, backref='token_first', verbose_name="первый токен", on_delete="CASCADE")
    second_id = ForeignKeyField(
        Token, unique=True, backref='token_first', verbose_name="второй токен", on_delete="CASCADE")

    class Meta:
        db_table = 'token_pair'

    @classmethod
    @logger.catch
    def add_pair(cls, first: int, second: int) -> int:
        """add pair related tokens in table
            arguments:
                first_id: int
                second_id: int
        """
        if (cls.select().where((cls.first_id.in_((first, second)))
                               | (cls.second_id.in_((first, second)))).count()):
            return 0
        pair = [{'first_id': first, 'second_id': second},
                {'first_id': second, 'second_id': first}
                ]
        return cls.insert(pair).execute()

    @classmethod
    @logger.catch
    def delete_pair(cls, token_id: int) -> bool:
        """delete pair related tokens from table
            arguments:
                token_id: int
        """
        return bool(cls.delete().
            where((cls.first_id == token_id) | (cls.second_id == token_id)).execute())

    @classmethod
    @logger.catch
    def remove_pairs_from_list(cls, token_list: list) -> int:
        """remove  pairs from the list
            arguments:
                token_list: list
        """
        return (cls.delete().where((cls.first_id.in_(token_list))
                                   | (cls.second_id.in_(token_list))).execute())

    @classmethod
    @logger.catch
    def remove_all_pairs(cls) -> int:
        """remove all relations of tokens
            arguments:
                token_id: int"""
        return cls.delete().execute()

    @classmethod
    @logger.catch
    def _get_all_related_tokens(cls) -> Tuple[int, ...]:
        """select all related tokens"""
        first = cls.select(cls.first_id.alias('token'))
        second = cls.select(cls.second_id.alias('token'))
        query = first | second

        return tuple([value.token for value in query.execute()])

    @classmethod
    @logger.catch
    def get_token_mate(cls, token_id: str) -> Token:
        """get mate for token"""
        pair = cls.select().where((cls.first_id == token_id) | (cls.second_id == token_id)).first()
        if pair:
            return pair.first_id if pair.second_id_id == int(token_id) else pair.second_id


@logger.catch
def drop_db() -> None:
    """Deletes all tables in database"""

    with db:
        try:
            db.drop_tables([User, Token, TokenPair, Proxy], safe=True)
            logger.info('DB deleted')
        except Exception as err:
            logger.error(f"Ошибка удаления таблиц БД: {err}")


@logger.catch
def recreate_db(_db_file_name: str = None) -> None:
    """Creates new tables in database. Drop all data from DB if it exists."""

    with db:
        if _db_file_name and os.path.exists(_db_file_name):
            drop_db()
        db.create_tables([User, Token, TokenPair, Proxy, UserChannel, Channel], safe=True)
        logger.info('DB REcreated')


if __name__ == '__main__':
    recreate = 0
    add_test_users = 0
    add_admins = 0
    add_tokens = 0
    set_max_tokens = 0
    set_proxy = 0
    import random
    import string

    test_user_list = (
        (f'test{user}', ''.join(random.choices(string.ascii_letters, k=5)))
        for user in range(1, 6)
    )
    # if add_tokens:
    #     # user_id = User.get_user_id_by_telegram_id('test2')
    #     [
    #         (UserTokenDiscord.add_token_by_telegram_id(user_id, f'{user_id}token{number}'))
    #         for user_id in ('test1', 'test3', 'test5') for number in range(1, 4)
    #     ]
    if recreate:
        recreate_db(DB_FILE_NAME)

    if add_admins:
        for idx, admin_id in enumerate(admins_list, start=1):
            t_nick_name = f"Admin_{idx}"
            User.add_new_user(nick_name=t_nick_name, telegram_id=admin_id, proxy=DEFAULT_PROXY)

            User.set_user_status_admin(telegram_id=admin_id)
            User.activate_user(admin_id)
            logger.info(f"User {t_nick_name} with id {admin_id} created as ADMIN.")

    if set_max_tokens:
        t_telegram_id = ''
        t_max_tokens = 0
        User.set_max_tokens(telegram_id=t_telegram_id, max_tokens=t_max_tokens)
