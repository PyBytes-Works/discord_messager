from typing import List, Tuple, Any, Union
import datetime
import os
from itertools import groupby

from peewee import (
    Model, CharField, BooleanField, DateTimeField, ForeignKeyField, IntegerField, TimestampField,
    JOIN, Case, fn
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
    """The Channel class have fields guild and channel"""
    guild = CharField(
        default='0', max_length=30, unique=True, verbose_name="Гильдия для подключения"
    )
    channel = CharField(
        default='0', max_length=30, unique=True, verbose_name="Канал для подключения"
    )

    class Meta:
        table_name = 'channel'

    @classmethod
    @logger.catch
    def get_or_create_channel(cls: 'Channel', guild: Any, channel: Any) -> 'Channel':
        user_channel, created = cls.get_or_create(guild=guild, channel=channel)
        return user_channel

    # @classmethod
    # @logger.catch
    # def get_channel(cls: 'Channel', guild: Any, channel: Any) -> 'Channel':
    #     return cls.get(guild=guild, channel=channel)


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
                     .group_by(Proxy.proxy).order_by(fn.COUNT(cls.id)).where(1 == 1)
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
        """TODO Нахрена? удялить при деактивации
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
    def get_all_users(cls: 'User') -> dict:
        """
        returns dict of all users
        return: dict
        """
        timestamp = datetime.datetime.fromtimestamp
        return {
            user.telegram_id: (
                f'{user.nick_name.rsplit("_", maxsplit=1)[0]} | '
                f'{"Active" if user.active else "Not active"} | '
                f'{"Admin" if user.admin else "Not admin"} | '
                f'Proxy: {user.proxy if user.proxy else "ЧТО ТО СЛОМАЛОСЬ"} | '
                f'\nID: {user.telegram_id if user.telegram_id else "ЧТО ТО СЛОМАЛОСЬ"} | '
                f'№: {user.max_tokens if user.max_tokens else "ЧТО ТО СЛОМАЛОСЬ"} | '
                f'{timestamp(user.expiration) if user.expiration else "ЧТО ТО СЛОМАЛОСЬ"}'
                )
            for user in User.select().execute()
        }

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
        set max tokens for user
        subscription_period:  int
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
            return user.proxy.name

    @classmethod
    @logger.catch
    def get_max_tokens(cls: 'User', telegram_id: str) -> int:
        """
        Возвращает максимальное количество токенов для пользователя
        """
        user = cls.get_or_none(cls.max_tokens, cls.telegram_id == telegram_id)
        if user:
            return user.max_tokens
        return 0

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

    @classmethod
    @logger.catch
    def unwork_all_users(cls):
        return cls.update(is_work=False).execute()

    @classmethod
    @logger.catch
    def work_all_users(cls):
        now = datetime.datetime.now().timestamp()
        return cls.update(active=True).where(cls.expiration > now).execute()


class UserChannel(BaseModel):
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
            cls,
            telegram_id: str,
            name: str,
            guild: Union[str, int],
            channel: Union[str, int],
            cooldown: int = 60) -> 'UserChannel':
        """
        TODO гильдия и какнал перевести в бигинт
        Функция создает запись связи пользователя с дискорд каналом
        если канала нет, он будет создан
        """
        user = User.get_user_by_telegram_id(telegram_id=telegram_id)
        channel = Channel.get_or_create_channel(guild=guild, channel=channel)
        return cls.create(user=user, name=name, channel=channel.id, cooldown=cooldown)

    @classmethod
    @logger.catch
    def get_user_channel(
            cls, telegram_id: Union[str, int], channel: Union[str, int]) -> 'UserChannel':
        """
        Функция получает запись пользователя о канале
        """
        user = User.get_user_by_telegram_id(telegram_id=telegram_id)
        return cls.select().union(Channel).where(cls.user == user, Channel.channel_id == channel)

    @classmethod
    @logger.catch
    def get_all_user_channel_by_telegram_id(
            cls, telegram_id: Union[str, int]) -> 'UserChannel':
        """
        Функция получает запись пользователя о канале
        """
        user = User.get_user_by_telegram_id(telegram_id=telegram_id)
        return (
                    cls.select(cls)
                    .join(Channel, UserChannel.channel == Channel.channel_id)
                    .where(UserChannel.user == user)
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
          get_token_by_discord_id
          check_token_by_discord_id
          update_token_cooldown
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
    # TODO kill cooldown = IntegerField(
    #     default=60*5, verbose_name="Время отправки последнего сообщения"
    # )
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
        count_tokens = (
                        Token.select()
                        .join(UserChannel, on=(Token.user_channel == UserChannel.id))
                        .join(User, on=(UserChannel.user == User.id))
                        .where(User.id == user_channel.user).count()
        )
        limit = user_channel.user.max_tokens > count_tokens
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

    # @classmethod
    # @logger.catch
    # def update_token_cooldown(cls, token: str, cooldown: int) -> bool:
    #     """
    #     set cooldown: update cooldown in seconds for token
    #     token: (str)
    #     cooldown: (int) seconds
    #     """
    #
    #     cooldown = cooldown if cooldown > 0 else 5 * 60
    #     return cls.update(cooldown=cooldown).where(cls.token == token).execute()

    # @classmethod
    # @logger.catch
    # def update_mate_cooldown(cls, token: str, cooldown: int) -> bool:
    #     """set cooldown in seconds to token mate"""
    #     # TODO кулдаун не тут
    #     my_token: 'Token' = cls.get_or_none(cls.token == token)
    #     mate: TokenPair = TokenPair.get_token_mate(my_token.id)
    #     return cls.update_token_cooldown(token=mate.token, cooldown=cooldown)

    @classmethod
    @logger.catch
    def make_tokens_pair(cls, first: Union[int, str], second: Union[int, str]) -> bool:
        """
        make pair
             first_id: (str) or int
             second_id: (str)
             unites tokens in pair
             TODO test
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
    def get_all_related_user_tokens(cls, telegram_id: Union[str, int] = None) -> List:
        """
        Вернуть список всех связанных ТОКЕНОВ пользователя по его telegram_id:
        return: data Список объектов с нужными полями
        TODO определится с составом полей, рефакторинг возможно по таблице пар начиная от юзера
        """
        query = (cls.select(
            cls.token.alias('token'),
            cls.name.alias('name'),
            UserChannel.name.alias('user_channel'),
            Channel.channel.alias('channel'),
            User.nick_name.alias('user_name'),
            Case(None, [((TokenPair.first_id == cls.id),
                         TokenPair.second_id,)], TokenPair.first_id).alias('pair_id')
        )
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
    def get_all_user_tokens(cls, telegram_id: Union[str, int] = None) -> List:
        """ TODO если подойдёт верхняя в этом методе нет смысла
        Вернуть список всех ТОКЕНОВ пользователя по его telegram_id:
        return: data Список объектов с нужными полями
        TODO определится с составом полей, рефакторинг возможно по таблице пар начиная от юзера
        """
        query = (cls.select(
            cls.token.alias('token'),
            cls.id.alias('id'),
            cls.name.alias('name'),
            UserChannel.name.alias('user_channel'),
            Channel.channel.alias('channel'),
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

    @classmethod
    @logger.catch
    def get_all_tokens_by_user(cls, user_id: str) -> List['Token']:
        """
        TODO сомнительный метод проверить нужность
        Вернуть список всех ТОКЕНОВ пользователя по его id:
        return: список token
        """
        result = cls.select().where(cls.user == user_id).execute()
        return [data for data in result] if result else []

    # @classmethod
    # @logger.catch
    # def get_all_discord_id(cls, token: str) -> List[str]:
    #     """
    #     TODO обсудить скорее всего тоже лишнее, нужно возвращать по каналу
    #     Вернуть список всех дискорд ID пользователя по его токену:
    #     return: (list) список discord_id
    #     """
    #     data = (cls.select(cls.name).)
    #     token = Token.get_or_none(token=token)
    #     tokens = None
    #     if token:
    #         user_id = token.user
    #         tokens = cls.select().where(cls.user == user_id).execute()
    #     return [data.discord_id for data in tokens] if tokens else []

    @classmethod
    @logger.catch
    def get_all_discord_id_by_channel(cls, user_channel: int) -> List[str]:
        """
        Вернуть список всех дискорд ID в канале:
        return: (list) список discord_id
        TODO test
        """
        # FIXME скорее всего метод нужно перенести в пользовательские каналы
        tokens = cls.select(Token.discord_id).where(cls.user_channel == user_channel).execute()
        return [data.discord_id for data in tokens] if tokens else []

    # @classmethod
    # @logger.catch
    # def get_all_info_tokens(cls, telegram_id: str) -> list:
    #     """
    #     TODO скорее всего метод удалить
    #     Вернуть список всех ТОКЕНОВ пользователя по его telegram_id:
    #     return: список словарей
    #     {'token': str, 'guild':str, channel: str,
    #     'time':время_последнего_сообщения, 'cooldown': кулдаун}
    #     """
    #     def get_info(token_data: 'Token') -> dict:
    #         if not token_data:
    #             return {}
    #         mate_token: 'TokenPair' = TokenPair.get_token_mate(token_id=token_data.id)
    #         mate_discord_id: int = mate_token.discord_id if mate_token else None
    #         return {
    #             'token_id': token_data.id,
    #             'token': token_data.token,
    #             'discord_id': token_data.discord_id,
    #             'mate_id': mate_discord_id,
    #             # 'guild': token_data.guild,
    #             # 'channel': token_data.channel,
    #             'time': token_data.last_message_time,
    #             'cooldown': token_data.cooldown
    #             }
    #
    #     user: 'User' = User.get_user_by_telegram_id(telegram_id)
    #     if user:
    #         discord_tokens = cls.select().where(cls.user == user.id).execute()
    #         return [get_info(token) for token in discord_tokens]
    #
    #     return []

    @classmethod
    @logger.catch
    def get_all_free_tokens(cls, telegram_id: Union[str, int] = None) -> Tuple:
        """
        TODO тоже под вопросом но возможно нужен
        Возвращает список всех свободных токенов по каналам
        если ввести телеграмм id
        ограничивает выбору одним пользователем
        """
        query = (
                 cls.select(
                    cls.token.alias('token'),
                    cls.name.alias('name'),
                    UserChannel.name.alias('user_channel'),
                    Channel.channel.alias('channel'),
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
        TODO нужен ли?
        """
        data = cls.select().where(cls.discord_id == discord_id).execute()
        return True if data else False

    @classmethod
    @logger.catch
    def get_info_by_token(cls, token: str) -> List:
        """
        Вернуть info по токену
        возвращает объект токен
            'proxy':proxy(str), 'guild':guild(int), 'channel': channel(int), 'language':
                language(str), 'last_message_time': last_message_time(int, timestamp),
                'cooldown': cooldown(int, seconds)}
                если токена нет приходит пустой словарь
                guild, channel по умолчанию 0 если не было изменений вернётся 0
                proxy по умолчанию пусто
                cooldown по умолчанию 5 * 60
        """
        query = (
                 cls.select(
                    cls.token.alias('token'),
                    cls.name.alias('name'),
                    UserChannel.name.alias('user_channel'),
                    Channel.channel.alias('channel'),
                    User.nick_name.alias('user_name'),
                 )
                 .join_from(cls, UserChannel, JOIN.LEFT_OUTER,
                            on=(cls.user_channel == UserChannel.id))
                 .join_from(cls, Channel, JOIN.LEFT_OUTER, on=(UserChannel.channel == Channel.id))
                 .join_from(cls, User, JOIN.LEFT_OUTER, on=(UserChannel.user == User.id))
                 .join_from(cls, TokenPair, JOIN.LEFT_OUTER,
                            on=((TokenPair.first_id == cls.id) | (TokenPair.second_id == cls.id)))

                 .where(Token.token == token).namedtuples()
                 )
        result = query.first()
        return result

    @classmethod
    @logger.catch
    def delete_token(cls, token: str) -> int:
        #
        """Удалить токен по его "значению": TODO тест"""
        # token = cls.get_or_none(cls.token == token)
        # if token:
        #     TokenPair.delete_pair(token.id)
        #     return token.delete_instance()
        return cls.delete().where(cls.token == token).execute()

    @classmethod
    @logger.catch
    def delete_token_by_id(cls, token_id: str):
        """Удалить токен по его "pk": TODO тест """
        return cls.delete().where(cls.id == token_id).execute()

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
        TODO ачем? легче удалять каналы пользователя токены автоматом грохнутся
        removes all tokens for user
        return: number of removed tokens
        """
        pass
        # result = Token.get_all_tokens_by_user(user_id=user.id)
        # tokens = [data.id for data in result]
        # TokenPair.remove_pairs_from_list(token_list=tokens)
        # return cls.delete().where(cls.user == user).execute()

    # @classmethod
    # @logger.catch
    # def get_number_of_free_slots_for_tokens(cls, telegram_id: str) -> int:
    #     """
    #     Вернуть количество свободных мест для размещения токенов
    #     """
    #     user = User.get_user_by_telegram_id(telegram_id)
    #     if user:
    #         max_tokens = user.max_tokens
    #         count_tokens = cls.select().where(cls.user == user.id).count()
    #
    #         return max_tokens - count_tokens

    @classmethod
    @logger.catch
    def get_token_by_discord_id(cls, discord_id: str) -> 'Token':
        """
        TODO нужно ли
        Вернуть token по discord_id
        """
        token: 'Token' = cls.get_or_none(discord_id=discord_id)

        return token


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
    def get_all_related_tokens(cls) -> Tuple[int, ...]:
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
