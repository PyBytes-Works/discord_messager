from collections import namedtuple
from typing import List, Tuple, Any, Union
import datetime
import os

from peewee import (
    Model, CharField, BooleanField, DateTimeField, ForeignKeyField, IntegerField, TimestampField,
    JOIN, Case, fn, BaseQuery, BigIntegerField
)

from config import logger, admins_list, db, db_file_name, DEFAULT_PROXY


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
            update_proxies_for_owners
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
    def get_proxy_count(cls) -> bool:
        return cls.select().count()

    @classmethod
    @logger.catch
    def delete_proxy(cls, proxy: str) -> bool:
        instance: cls = cls.get_or_none(proxy=proxy)
        if instance:
            return instance.delete_instance()
        return False

    @classmethod
    @logger.catch
    def get_list_proxies(cls: 'Proxy') -> tuple:
        """return Tuple[Tuple[str, int]] or () """
        result = cls.get()
        return [(inst.proxy, inst.using) for inst in result] if result else ()

    @classmethod
    @logger.catch
    def get_low_used_proxy(cls: 'Proxy') -> str:
        """
        Возвращает первую прокси с самым малым использованием
            return: str
        """
        result = cls.select().order_by(cls.using).execute()[:1]
        if result:
            return result[0].proxy

    @classmethod
    @logger.catch
    def update_proxies_for_owners(cls: 'Proxy', proxy: str) -> int:
        """
        Метод получает не рабочую порокси, удаляет ее и
        перезаписывает прокси для всех пользователей
            methods:
                get_or_create
        """
        cls.delete_proxy(proxy=proxy)
        if not cls.get_proxy_count():
            return 0
        users = User.select().where(User.proxy == proxy).execute()
        count = 0
        for user in users:
            new_proxy = cls.get_low_used_proxy()
            count += 1
            User.set_proxy_by_telegram_id(telegram_id=user.telegram_id, proxy=new_proxy)
        return count


class Channel(BaseModel):
    """The Channel class have fields guild_id and channel_id"""
    guild_id = BigIntegerField(unique=True, verbose_name="Гильдия для подключения")
    channel_id = BigIntegerField(unique=True, verbose_name="Канал для подключения")

    class Meta:
        table_name = 'channel'

    @classmethod
    @logger.catch
    def get_or_create_channel(cls: 'Channel', guild_id: Any, channel_id: Any) -> 'Channel':
        user_channel, created = cls.get_or_create(guild_id=guild_id, channel_id=channel_id)
        return user_channel

    # @classmethod
    # @logger.catch
    # def get_channel(cls: 'Channel', guild_id: Any, channel_id: Any) -> 'Channel':
    #     return cls.get(guild_id=guild_id, channel_id=channel_id)


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
    expiration = TimestampField(
        default=datetime.datetime.now().timestamp(),
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
            expiration: int = 24
    ) -> 'User':
        """
        if the user is already in the database, returns None
        if created user will return user id
        nik_name: str
        telegram_id: str
                # proxy: str
        expiration: int  (hours)
        return: str
        """
        user = cls.select().where(cls.telegram_id == telegram_id).count()
        if not user:
            expiration = 100 * 365 * 24 if expiration == -1 else expiration
            expiration = int(datetime.datetime.now().timestamp()) + expiration * 60 * 60
            proxy = (cls.select(Proxy.id)
                     .join(Proxy, JOIN.RIGHT_OUTER, on=(Proxy.id == User.proxy))
                     .group_by(Proxy.proxy).order_by(fn.COUNT(cls.id))
                     .limit(1).namedtuples().first())
            proxy_id = proxy if proxy.id else None
            result = cls.create(
                            nick_name=f'{nick_name}_{telegram_id}',
                            telegram_id=telegram_id,
                            proxy=proxy_id,
                            expiration=expiration,
                        )

            return result

    @classmethod
    @logger.catch
    def delete_user_by_telegram_id(cls: 'User', telegram_id: str) -> tuple:
        """
        delete user by telegram id
        #
        """
        return cls.delete().where(cls.telegram_id == telegram_id).execute

    @classmethod
    @logger.catch
    def delete_all_tokens(cls, telegram_id: str) -> int:
        """TODO Нахрена? удялить при деактивации? ждем Артема?
        удаляет пользовательские каналы
        """
        return UserChannel.delete().where(
                        UserChannel.user.in_(cls.select(User.id)
                            .where(cls.telegram_id == telegram_id)
                            )
                    ).execute()

    @classmethod
    @logger.catch
    def delete_all_pairs(cls: 'User', telegram_id: str) -> bool:
        """
        remove all associations of user token pairs and User channels
        """

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
        )

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
    def get_all_inactive_users(cls: 'User') -> dict:
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
    def get_all_users(cls: 'User') -> BaseQuery.namedtuples:
        """
        returns dict of all users
        return: named tuple
        list of namedtuple fields:
            nick_name: str
            user_active: str
            user_admin: str
            proxy: str
            telegram_id: str
            max_token: int
            user_expiration: timestamp
        """
        return User.select(
            User.nick_name.alias('nick_name'),
            Case(None, [((User.active == True), 'Active',)], 'Not active').alias('user_active'),
            Case(None, [((User.admin == True), 'Admin',)], 'Not admin').alias('user_admin'),
            Proxy.proxy.alias('proxy'),
            User.telegram_id.alias('telegram_id'),
            User.telegram_id.alias('telegram_id'),
            User.max_tokens.alias('max_token'),
            User.expiration.alias('user_expiration'),
        ).join(Proxy, JOIN.LEFT_OUTER, on=(User.proxy == Proxy.id)).execute()
                # f'{user.nick_name.rsplit("_", maxsplit=1)[0]} | '
                # f'{"Active" if user.active else "Not active"} | '
                # f'{"Admin" if user.admin else "Not admin"} | '
                # f'Proxy: {user.proxy.proxy if user.proxy else "ЧТО ТО СЛОМАЛОСЬ"} | '
                # f'\nID: {user.telegram_id if user.telegram_id else "ЧТО ТО СЛОМАЛОСЬ"} | '
                # f'№: {user.max_tokens if user.max_tokens else "ЧТО ТО СЛОМАЛОСЬ"} | '
                # f'{timestamp(user.expiration) if user.expiration else "ЧТО ТО СЛОМАЛОСЬ"}'

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
        """ Возвращает список пользователей которым должна отправляться рассылка"""
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
    def set_proxy_by_telegram_id(cls: 'User', telegram_id: str, proxy_pk: int) -> bool:
        """
        set proxy for user
        telegram_id:  str
        proxy_pk:  int
        """
        return cls.update(proxy=proxy_pk).where(cls.telegram_id == telegram_id).execute

    @classmethod
    @logger.catch
    def check_expiration_date(cls: 'User', telegram_id: str) -> bool:
        """
        Возвращает статус подписки пользователя,
        True если подписка ещё действует
        False если срок подписки истёк
        """

        user: User = cls.get_or_none(cls.telegram_id == telegram_id)
        expiration: int = user.expiration if user else 0

        return expiration > datetime.datetime.now().timestamp() if expiration else False

    @classmethod
    @logger.catch
    def get_expiration_date(cls: 'User', telegram_id: str) -> int:
        """
        Возвращает timestamp без миллисекунд в виде целого числа
        """
        user = cls.get_or_none(cls.expiration, cls.telegram_id == telegram_id)
        if user:
            expiration = user.expiration

            return expiration

    @classmethod
    @logger.catch
    def get_proxy(cls: 'User', telegram_id: str) -> CharField:
        """
        Возвращает прокси пользователя
        """
        user: User = cls.get_or_none(cls.proxy, cls.telegram_id == telegram_id)
        if user:
            return user.proxy.proxy

    @classmethod
    @logger.catch
    def get_max_tokens(cls: 'User', telegram_id: str) -> int:
        """
         Return the maximum number of tokens for a user
        """
        user = cls.get_or_none(cls.max_tokens, cls.telegram_id == telegram_id)
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
        now = datetime.datetime.now().timestamp()
        return cls.update(active=True).where(cls.expiration > now).execute()


class UserChannel(BaseModel):
    """
    class user channel for save user's channels and cooldown
    methods:
        add_user_channel
        get_user_channel
        get_all_user_channel_by_telegram_id
        update_cooldown_by_channel_id
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
            name: str,
            guild_id: int,
            channel_id: int,
            cooldown: int = 60) -> 'UserChannel':
        """
        Функция создает запись связи пользователя с дискорд каналом
        если канала нет, он будет создан
        """
        user = User.get_user_by_telegram_id(telegram_id=telegram_id)
        channel = Channel.get_or_create_channel(guild_id=guild_id, channel_id=channel_id)
        return cls.create(user=user, name=name, channel=channel.id, cooldown=cooldown)

    @classmethod
    @logger.catch
    def get_user_channel(
            cls: 'UserChannel', telegram_id: Union[str, int], channel_id: int
    ) -> BaseQuery.namedtuples:
        """
        Function return named tuple
            list of namedtuple fields:
            channel_name: str
            cooldown: int
            channel_id: int
            guild_id: int
        """
        return (cls.select(
                            cls.name.alias('channel_name'),
                            cls.name.alias('cooldown'),
                            Channel.channel_id.alias('channel_id'),
                            Channel.guild_id.alias('guild_id'),
                        )
                            .join(Channel, JOIN.LEFT_OUTER, on=(Channel.id == cls.channel))
                            .join(User, JOIN.LEFT_OUTER, on=(User.id == cls.user))
                            .where(User.telegram_id == telegram_id)
                            .where(cls.channel == channel_id).namedtuples().first())

    @classmethod
    @logger.catch
    def get_all_user_channel_by_telegram_id(
            cls: 'UserChannel', telegram_id: Union[str, int]) -> List[BaseQuery.namedtuples]:
        """
        Function returns a list of named tuples
        list of namedtuple fields:
            channel_name: str
            cooldown: int
            channel_id: int
            guild_id: int
        """
        return list(
                    cls.select(
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
    def update_cooldown_by_channel_id(cls: 'UserChannel', chanel_id: int, cooldown: int) -> int:
        """
        Update cooldown for all users_channel by channel_id
            TODO логично было бы всем но можно конкретному
        """
        return (
            cls.update(cooldown=cooldown)
            .where(
                cls.channel.in_(
                    Channel.select(Channel.id).where(Channel.channel_id == chanel_id)
                )
            )
        )


class Token(BaseModel):
    """
    Model for table discord_users
      methods:
          add_token_by_telegram_id
          delete_inactive_tokens
          delete_tokens_by_user
          is_token_exists
          get_all_user_tokens
          get_all_info_tokens
          get_number_of_free_slots_for_tokens
          get_time_by_token
          get_info_by_token
          get_all_free_tokens
          get_all_discord_id
          get_all_discord_id_by_channel
          check_token_by_discord_id
          update_token_time
    """
    # user = ForeignKeyField(User, on_delete="CASCADE")
    user_channel = ForeignKeyField(
        UserChannel, backref='token', verbose_name="Канал для подключения", on_delete='CASCADE')
    name = CharField(max_length=100, verbose_name="Название токена")
    token = CharField(max_length=255, unique=True, verbose_name="Токен пользователя в discord")
    discord_id = CharField(max_length=255, unique=True, verbose_name="ID пользователя в discord")

    language = CharField(
        default='en', max_length=10, unique=False, verbose_name="Язык канала в discord"
    )
    last_message_time = TimestampField(
        default=datetime.datetime.now().timestamp() - 60*5,
        verbose_name="Время отправки последнего сообщения"
    )

    class Meta:
        db_table = "tokens"

    @classmethod
    @logger.catch
    def is_token_exists(cls, token: str) -> bool:
        return bool(cls.select().where(cls.token == token).count())

    @classmethod
    @logger.catch
    def add_token_by_user_channel(
                                    cls,
                                    telegram_id: Union[str, int],
                                    token: str,
                                    discord_id: str,
                                    user_channel: 'UserChannel',
                                    name: str,
                                 ) -> bool:

        """
        Add a new token to the client channel
        return: bool True if write was successful,
        False if this token or discord_id already exists in the database
        or the number of tokens is equal to the limit
        """

        limit = cls.get_number_of_free_slots_for_tokens(telegram_id=telegram_id)
        answer = False
        if limit:
            token, answer = cls.get_or_create(
                user_channel=user_channel,
                name=name,
                token=token,
                discord_id=discord_id,
                )
        return answer

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
    def make_tokens_pair(cls, first: Union[int, str], second: Union[int, str]) -> bool:
        """
        make pair
             first_id: (str) or int
             second_id: (str)
             unites tokens in pair
        """
        token_first: cls = cls.select().where(cls.token == first).first()
        if not token_first:
            return False
        token_second = (cls.select()
                        .where(cls.token == second, cls.user_channel == token_first.user_channel)
                        .first())
        if not token_second:
            return False
        result = TokenPair.add_pair(first=token_first.id, second=token_second.id)
        return bool(result)

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
    def get_related_tokens(cls, telegram_id: Union[str, int] = None) -> List[BaseQuery.namedtuples]:
        """
        Вернуть список всех связанных ТОКЕНОВ пользователя по его telegram_id:
        return: data список словарей
        token str
        cooldown  int
        last_message_time Timestamp
        """
        query = (cls.select(
            cls.token.alias('token'),
            cls.last_message_time.alias('last_message_time'),
            UserChannel.name.alias('channel_name'))
                 .join_from(cls, UserChannel, JOIN.LEFT_OUTER, on=(
                    cls.user_channel == UserChannel.id))
                 .join_from(cls, Channel, JOIN.LEFT_OUTER, on=(UserChannel.channel == Channel.id))
                 .join_from(cls, User, JOIN.LEFT_OUTER, on=(UserChannel.user == User.id))
                 .join_from(cls, TokenPair, JOIN.RIGHT_OUTER,
                    on=((TokenPair.first_id == cls.id) | (TokenPair.second_id == cls.id)))
                 .where(User.telegram_id == telegram_id).namedtuples()
                 )
        return [data for data in query]

    @classmethod
    @logger.catch
    def get_all_tokens_info(cls, telegram_id: Union[str, int] = None) -> List[BaseQuery.namedtuples]:
        """ TODO если подойдёт верхняя в этом методе нет смысла
        Вернуть список всех ТОКЕНОВ пользователя по его telegram_id:
        return:
        TODO как вверху но добавить описательное для юзера имена каналов имена токенов
        token str
        token_discord_id str
        proxy str
        user_channel_pk int
        channel_id int
        guild_id int
        cooldown  int
        mate_id str (discord_id)
        """
        query = (cls.select(
            cls.token.alias('token'),
            cls.id.alias('id'),
            cls.name.alias('name'),
            UserChannel.name.alias('user_channel'),
            Channel.channel_id.alias('channel_id'),
            User.nick_name.alias('user_name'),
            Case(None, [((TokenPair.first_id == cls.id),
                         TokenPair.second_id,)], TokenPair.first_id).alias('pair_id')
        )
                 .join_from(cls, UserChannel, JOIN.LEFT_OUTER, on=(
                    cls.user_channel == UserChannel.id))
                 .join_from(cls, Channel, JOIN.LEFT_OUTER, on=(UserChannel.channel == Channel.id))
                 .join_from(cls, User, JOIN.LEFT_OUTER, on=(UserChannel.user == User.id))
                 .join_from(cls, TokenPair, JOIN.LEFT_OUTER,
                            on=((cls.id == TokenPair.first_id) | (cls.id == TokenPair.second_id)))
                 .where(User.telegram_id == telegram_id).namedtuples()
                 )
        return [data for data in query]

    # @classmethod
    # @logger.catch
    # def get_all_discord_id(cls, user_channel: int) -> List[str]:
    #     """
    #     TODO Вернуть список всех дискорд ID пользователя по его токену:
    #     return: (list) список discord_id
    #     """
    #     pass
        # data = (cls.select(cls.name).)
        # token = Token.get_or_none(token=token)
        # tokens = None
        # if token:
        #     user_id = token.user
        #     tokens = cls.select().where(cls.user == user_id).execute()
        # return [data.discord_id for data in tokens] if tokens else []

    @classmethod
    @logger.catch
    def get_all_discord_id_by_channel(cls, user_channel_pk: int) -> List[str]:
        """
        TODO  Вернуть список всех дискорд ID в пользовательском канале:
        return: (list) список discord_id
        TODO
        """
        # FIXME метод нужно перенести в пользовательские каналы ДА
        pass

    @classmethod
    @logger.catch
    def get_all_free_tokens(cls, telegram_id: Union[str, int] = None) -> Tuple[List[int]]:
        """
        TODO  нужен Tuple[List[token_pk]]
        Возвращает список всех свободных токенов по каналам
        если ввести телеграмм id
        ограничивает выбору одним пользователем
        discord id
        """

        query = (
                 cls.select(
                    cls.token.alias('token'),
                    cls.name.alias('name'),
                    UserChannel.name.alias('user_channel'),
                    Channel.channel_id.alias('channel_id'),
                    User.nick_name.alias('user_name'),
                 )
                 .join_from(cls, UserChannel, JOIN.LEFT_OUTER, on=(
                        cls.user_channel == UserChannel.id))
                 .join_from(cls, Channel, JOIN.LEFT_OUTER, on=(UserChannel.channel == Channel.id))
                 .join_from(cls, User, JOIN.LEFT_OUTER, on=(UserChannel.user == User.id))
                 .join_from(cls, TokenPair, JOIN.LEFT_OUTER,
                            on=((TokenPair.first_id == cls.id) | (TokenPair.second_id == cls.id)))

                .where(User.telegram_id == telegram_id)
                .where(TokenPair.first_id == None).namedtuples()
        )
        return tuple([data for data in query])

    @classmethod
    @logger.catch
    def get_time_by_token(cls, token: str) -> int:
        """
        Вернуть timestamp(кд) токена по его "значению":
        TODO test
        """
        data = cls.get_or_none(cls.last_message_time, cls.token == token)
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
    def get_info_by_token(cls, token: str) -> dict:
        """
        TODO сделать как в документации
        Вернуть info по токену
        возвращает объект токен
            'user_channel_pk' int
            'proxy':proxy(str),
            'guild_id':guild_id(int),
            'channel_id': channel_id(int),
            'cooldown': cooldown(int, seconds)}
            'mate_id' str (discord_id)
            'discord_id' str
        """
        # query = (
        #          cls.select(
        #             cls.token.alias('token'),
        #             cls.name.alias('name'),
        #             UserChannel.name.alias('user_channel'),
        #             Channel.channel_id.alias('channel_id'),
        #             User.nick_name.alias('user_name'),
        #          )
        #          .join_from(cls, UserChannel, JOIN.LEFT_OUTER,
        #                     on=(cls.user_channel == UserChannel.id))
        #          .join_from(cls, Channel, JOIN.LEFT_OUTER, on=(UserChannel.channel == Channel.id))
        #          .join_from(cls, User, JOIN.LEFT_OUTER, on=(UserChannel.user == User.id))
        #          .join_from(cls, TokenPair, JOIN.LEFT_OUTER,
        #                     on=((TokenPair.first_id == cls.id) | (TokenPair.second_id == cls.id)))
        #
        #          .where(Token.token == token).namedtuples()
        #          )
        # result = query.first()
        return 'result'

    @classmethod
    @logger.catch
    def delete_token(cls, token: str) -> int:
        """Удалить токен по его "значению": TODO тест"""

        return cls.delete().where(cls.token == token).execute()

    @classmethod
    @logger.catch
    def delete_inactive_tokens(cls) -> int:
        """ TODO зачем? легче удалять каналы пользователя токены автоматом грохнутся
        removes all tokens for inactive users
        return: number of removed tokens
        """
        pass
        # users = User.get_id_inactive_users()
        # return cls.delete().where(cls.user.in_(users)).execute()

    @classmethod
    @logger.catch
    def delete_tokens_by_user(cls, user: User) -> int:
        """
        TODO зачем? легче удалять каналы пользователя токены автоматом грохнутся
        removes all tokens for user
        return: number of removed tokens
        """
        pass
        # result = Token.get_all_tokens_by_user(user_id=user.id)
        # tokens = [data.id for data in result]
        # TokenPair.remove_pairs_from_list(token_list=tokens)
        # return cls.delete().where(cls.user == user).execute()

    @classmethod
    @logger.catch
    def get_number_of_free_slots_for_tokens(cls, telegram_id: str) -> int:
        """
        TODO доработать
        Вернуть количество свободных мест для размещения токенов
        """

        limit = (User.select(
                    Case(None,
                    [
                        ((fn.MAX(User.max_tokens).is_null(False)),
                            fn.MAX(User.max_tokens) - fn.COUNT(Token.id), )
                    ], 0).alias('limit'))
                    .join(UserChannel, JOIN.LEFT_OUTER, on=(UserChannel.user == User.id))
                    .join(cls, JOIN.LEFT_OUTER, on=(cls.user_channel == UserChannel.id))
                    .where(User.telegram_id == telegram_id).first())

        return limit


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
            return False
        pair = cls.create(first_id=first, second_id=second)
        return 1 if pair else 0

    @classmethod
    @logger.catch
    def delete_pair(cls, token_id: int) -> bool:
        """delete pair related tokens from table
            arguments:
                token_id: int
        """
        return (cls.delete().
                where((cls.first_id == token_id) | (cls.second_id == token_id)).execute())

    @classmethod
    @logger.catch
    def remove_pairs_from_list(cls, token_list: list) -> bool:
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
        recreate_db(db_file_name)

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

    if set_proxy:
        t_telegram_id = ''
        t_proxy = ""
        User.set_proxy_by_telegram_id(telegram_id=t_telegram_id, proxy=t_proxy)
