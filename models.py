from typing import List, Tuple, Optional, Any
import datetime
import os
from itertools import groupby

from peewee import (
    CharField, BooleanField, DateTimeField, ForeignKeyField, IntegerField
)
from peewee import Model, fn
from config import logger, admins_list, db, db_file_name, DEFAULT_PROXY


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
        # TODO test delete_all_pairs
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
    expiration = IntegerField(
        default=datetime.datetime.now().timestamp(),
        verbose_name='Срок истечения подписки'
    )
    proxy = CharField(max_length=50, default='', verbose_name="Прокси")

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
    def add_new_user(cls: 'User', nick_name: str, telegram_id: str, proxy: str = '', expiration: int=24) -> str:
        """
        if the user is already in the database, returns None
        if created user will return user id
        nik_name: str
        telegram_id: str
        proxy: str
        expiration: int  (hours)
        return: str
        """
        user = cls.get_or_none(cls.telegram_id == telegram_id)
        if not user:
            expiration = int(datetime.datetime.now().timestamp()) + expiration * 60 * 60
            return cls.create(
                nick_name=f'{nick_name}_{telegram_id}', telegram_id=telegram_id, proxy=proxy,
                expiration=expiration
            ).save()

    @classmethod
    @logger.catch
    def delete_user_by_telegram_id(cls: 'User', telegram_id: str) -> tuple:
        """
        delete user by telegram id
        """
        user = cls.get_or_none(cls.telegram_id == telegram_id)
        if user:
            user_id = user.id
            return (user.delete_instance(),
                    UserTokenDiscord.delete().where(UserTokenDiscord.user == user_id).execute())

    @classmethod
    @logger.catch
    def delete_all_pairs(cls: 'User', telegram_id: str) -> bool:
        """
        remove all associations of user token pairs
        """
        user = cls.get_or_none(cls.telegram_id == telegram_id)
        if user:
            result = UserTokenDiscord.get_all_tokens_by_user(user_id=user.id)
            tokens = [data.id for data in result]
            return TokenPair.remove_pairs_from_list(token_list=tokens)

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
                               # f'{"Work" if user.is_work else "Not work"} | '
                               f'{"Admin" if user.admin else "Not admin"} | ')
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
    def set_proxy_by_telegram_id(cls: 'User', telegram_id: str, proxy: str) -> bool:
        """
        set max tokens for user
        subscription_period:  int
        """
        return cls.update(proxy=proxy).where(cls.telegram_id == telegram_id).execute()

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
        if user:
            expiration = user.expiration
            return expiration

    @classmethod
    @logger.catch
    def get_proxy(cls: 'User', telegram_id: str) -> CharField:
        """
        возвращает timestamp без миллисекунд в виде целого числа
        """
        user: User = cls.get_or_none(cls.proxy, cls.telegram_id == telegram_id)
        # print(type(result.expiration))
        if user:
            return user.proxy

    @classmethod
    @logger.catch
    def get_max_tokens(cls: 'User', telegram_id: str) -> int:
        """
        возвращает максимальное количество токенов для пользователя
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


class UserTokenDiscord(BaseModel):
    """
    Model for table discord_users
      methods
      add_token_by_telegram_id
      delete_inactive_tokens
      get_all_user_tokens
      get_all_info_tokens
      get_number_of_free_slots_for_tokens
      get_time_by_token
      get_info_by_token
      Todo get_all_free_tokens
      TODO Token.get_all_discord_id(token=datastore.token) list all discord_id
      get_token_by_discord_id
      check_token_by_discord_id
      update_token_cooldown
      update_token_channel
      update_token_guild
      update_token_proxy
      update_token_time
    """
    user = ForeignKeyField(User, on_delete="CASCADE")
    token = CharField(max_length=255, unique=True, verbose_name="Токен пользователя в discord")
    discord_id = CharField(max_length=255, unique=True, verbose_name="ID пользователя в discord")
    mate_id = CharField(max_length=255, default='', verbose_name="ID напарника в discord")
    proxy = CharField(
        default='', max_length=25, unique=False, verbose_name="Адрес прокси сервера"
    )
    guild = CharField(
        default='0', max_length=30, unique=False, verbose_name="Гильдия для подключения"
    )
    channel = CharField(
        default='0', max_length=30, unique=False, verbose_name="Канал для подключения"
    )
    language = CharField(
        default='en', max_length=10, unique=False, verbose_name="Язык канала в discord"
    )
    cooldown = IntegerField(
        default=60*5, verbose_name="Время отправки последнего сообщения"
    )
    last_message_time = IntegerField(
        default=datetime.datetime.now().timestamp() - 60*5,
        verbose_name="Время отправки последнего сообщения"
    )

    class Meta:
        db_table = "user_token_discord"

    @classmethod
    @logger.catch
    def add_token_by_telegram_id(
                                    cls,
                                    telegram_id: str,
                                    token: str,
                                    discord_id: str,
                                    mate_id: str,
                                    proxy: str,
                                    guild: int,
                                    channel: int,
                                    language: str = 'en',
                                    cooldown: int = 60 * 5
                                 ) -> bool:

        """
        add token by telegram id
        FIXME
        return: bool or None если запись прошла то True, если такой токен есть то False,
        если нет такого пользователя None
        """
        user_id = User.get_user_by_telegram_id(telegram_id)
        if user_id:
            db_token: UserTokenDiscord = UserTokenDiscord.get_or_none(cls.token == token)
            if db_token:
                return False
            count_tokens = cls.select().where(cls.user == user_id).count()
            # count_tokens = cls.get_all_user_tokens(telegram_id)
            max_tokens = User.get_max_tokens(telegram_id)
            if max_tokens > int(count_tokens):
                new_token = {
                    'user': user_id,
                    'token': token,
                    'discord_id': discord_id,
                    'mate_id': mate_id,
                    'proxy': proxy,
                    'guild': guild,
                    'channel': channel,
                    'language': language,
                    'cooldown': cooldown,
                }

                return cls.get_or_create(**new_token)[-1]

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
        cooldown = cooldown if cooldown > 0 else 5 * 60
        return cls.update(cooldown=cooldown).where(cls.token == token).execute()

    @classmethod
    @logger.catch
    def make_token_pair(cls, first: Any, second: Any) -> bool:
        """
        make pair
             first: (str) or int
             second: (str)
             соединяет пару токенов
        """
        return TokenPair.add_pair(first=first, second=second)


    @classmethod
    @logger.catch
    def delete_token_pair(cls, token: str) -> None:
        """ FIXME
            Удаляет пару по токену
        """
        token_data: 'UserTokenDiscord' = UserTokenDiscord.get_or_none(token=token)
        if token_data:
            mate_id = token_data.mate_id
            discord_id = token_data.discord_id
            mate_data: 'UserTokenDiscord' = UserTokenDiscord.get_or_none(
                discord_id=mate_id, mate_id=discord_id)
            token_data.delete_instance()
            if mate_data:
                mate_data.delete_instance()

    @classmethod
    @logger.catch
    def update_token_language(cls, token: str, language: str) -> bool:
        """
        # TODO а надо ли
        set language: update language for token
         token: (str)
         language: (str)
        """
        return cls.update(language=language).where(cls.token == token).execute()

    @classmethod
    @logger.catch
    def update_token_guild(cls, token: str, guild: int) -> bool:
        """
        update guild: update guild by token
        token: (str)
        guild: (int) id guild
        """
        guild = str(guild) if guild > 0 else '0'
        return cls.update(guild=guild).where(cls.token == token).execute()

    @classmethod
    @logger.catch
    def update_token_channel(cls, token: str, channel: int) -> bool:
        """
        update channel: update channel by token
         token: (str)
         channel: (int) id channel
        """
        channel = str(channel) if channel > 0 else '0'
        return cls.update(channel=channel).where(cls.token == token).execute()

    @classmethod
    @logger.catch
    def update_token_proxy(cls, token: str, proxy: str) -> bool:
        """
        update proxy: update proxy by token
        token: (str)
        proxy: (str) ip address
        """
        return cls.update(proxy=proxy).where(cls.token == token).execute()

    @classmethod
    @logger.catch
    def update_token_info(cls, token: str, proxy: str, channel: int, guild: int) -> bool:
        """
        update guild, channel, proxy by token
        token: (str)
        proxy: (str) ip address
        """
        return cls.update(proxy=proxy, guild=guild, channel=channel).where(cls.token == token).execute()

    @classmethod
    @logger.catch
    def get_all_related_user_tokens(cls, telegram_id: Optional[str] = None) -> List[dict]:
        """
        # TODO test get_all_user_tokens

        Вернуть список всех связанных ТОКЕНОВ пользователя по его telegram_id:
        return: список словарей {token:{'time':время_последнего_сообщения,'cooldown': кулдаун}}
        """
        query = cls.select(cls.token, cls.last_message_time, cls.cooldown)
        related = TokenPair.get_all_related_tokens()
        if telegram_id:
            user_id: 'User' = User.get_user_by_telegram_id(telegram_id)
            if user_id:
                query = query.where(cls.user == user_id)
            else:
                return []
        result = query.where(cls.id.in_(related)).execute()
        return [
            {data.token: {'time': data.last_message_time, 'cooldown': data.cooldown}}
            for data in result
        ]

    @classmethod
    @logger.catch
    def get_all_tokens_by_user(cls, user_id: str) -> List['UserTokenDiscord']:
        """
        Вернуть список всех ТОКЕНОВ пользователя по его id:
        return: список token
        """
        result = cls.select().where(cls.user == user_id).execute()
        return [data for data in result] if result else []

    @classmethod
    @logger.catch
    def get_all_discord_id(cls, token: str) -> List[str]:
        """
        Вернуть список всех дискорд ID пользователя по его токену:
        return: (list) список discord_id
        """
        token = UserTokenDiscord.get_or_none(token=token)
        tokens = None
        if token:
            user_id = token.user
            tokens = cls.select().where(cls.user == user_id).execute()
        return [data.discord_id for data in tokens] if tokens else []

    @classmethod
    @logger.catch
    def get_all_info_tokens(cls, telegram_id: str) -> list:
        """
        Вернуть список всех ТОКЕНОВ пользователя по его telegram_id:
        return: список словарей
        {'token': str, 'guild':str, channel: str,
        'time':время_последнего_сообщения, 'cooldown': кулдаун}
        """
        def get_info(token_data: 'UserTokenDiscord') -> dict:
            if not token_data:
                return {}
            return {
                'token': token_data.token,
                'discord_id': token_data.discord_id,
                'mate_id': token_data.mate_id,
                'guild': token_data.guild,
                'channel': token_data.channel,
                'time': token_data.last_message_time,
                'cooldown': token_data.cooldown
                }

        user_id: 'User' = User.get_user_by_telegram_id(telegram_id)
        if user_id:

            data = []
            result = []
            for discord_token in cls.select().where(cls.user == user_id).execute():
                data.append(discord_token)
            while data:
                first: 'UserTokenDiscord' = data.pop()
                second = None
                for i, value in enumerate(data):
                    if first.mate_id == value.discord_id:
                        second = data.pop(i)
                        break
                result.append([get_info(first), get_info(second)])
            return result
        return []

    @classmethod
    @logger.catch
    def get_all_free_tokens(cls, telegram_id: Optional[str] = None) -> Tuple[Tuple[str, list], ...]:
        """
        TODO make this method
        Возвращает список всех токенов свободных токенов по каналам
        если ввести телеграмм id
        ограничивает выбору одним пользователем
        """
        related_tokens = TokenPair.get_all_related_tokens()
        data = cls.select(cls.id, cls.channel).where(cls.id.not_in(related_tokens))
        if telegram_id is not None:
            user = User.get_user_id_by_telegram_id(telegram_id=telegram_id)
            data = data.where(cls.user == user)
        data.order_by(cls.channel)

        data.order_by(cls.channel)
        res = [(chan, [tid.id for tid in rec]) for chan, rec in groupby(data, lambda x: x.channel)]
        return tuple(res)

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
    def check_token_by_discord_id(cls, discord_id: str) -> bool:
        """
        Вернуть timestamp(кд) токена по его "значению":
        """
        data = cls.select().where(cls.discord_id == discord_id).execute()
        return True if data else False

    @classmethod
    @logger.catch
    def get_info_by_token(cls, token: str) -> dict:
        """
        Вернуть info по токену
        возвращает словарь:

            {'proxy':proxy(str), 'guild':guild(int), 'channel': channel(int), 'language': language(str),
            'last_message_time': last_message_time(int, timestamp),  'cooldown': cooldown(int, seconds)}
            если токена нет приходит пустой словарь
            guild, channel по умолчанию 0 если не было изменений вернётся 0
            proxy по умолчанию пусто
            cooldown по умолчанию 5 * 60
        """
        result = {}
        data: 'UserTokenDiscord' = cls.get_or_none(cls.token == token)
        if data:
            guild = int(data.guild) if data.guild else 0
            channel = int(data.channel) if data.channel else 0
            result = {'proxy': data.proxy, 'discord_id': data.discord_id, 'guild': guild,
                      'channel': channel, 'mate_id': data.mate_id, 'language': data.language,
                      'last_message_time': data.last_message_time, 'cooldown': data.cooldown}
        return result

    @classmethod
    @logger.catch
    def delete_token(cls, token: str):
        # TODO  Delete relation token
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

    @classmethod
    @logger.catch
    def get_number_of_free_slots_for_tokens(cls, telegram_id: str) -> int:
        """
        Вернуть количество свободных мест для размещения токенов
        """
        user = User.get_user_by_telegram_id(telegram_id)
        if user:
            max_tokens = user.max_tokens
            count_tokens = cls.select().where(cls.user == user.id).count()

            return max_tokens - count_tokens

    @classmethod
    @logger.catch
    def get_token_by_discord_id(cls, discord_id: str) -> 'UserTokenDiscord':
        """
        Вернуть token по discord_id
        """
        token: 'UserTokenDiscord' = cls.get_or_none(discord_id=discord_id)

        return token


class TokenPair(BaseModel):
    """
    class for a table of related token pairs
        Methods:
            add_pair
            delete_pair
            remove_all_pairs
            get_all_related_tokens
     """

    first = ForeignKeyField(UserTokenDiscord, unique=True, verbose_name="первый токен")
    second = ForeignKeyField(UserTokenDiscord, unique=True, verbose_name="второй токен")

    class Meta:
        db_table = 'token_pair'

    @classmethod
    @logger.catch
    def add_pair(cls, first: int, second: int) -> bool:
        """add pair related tokens in table
            arguments:
                first: int
                second: int
        """
        if cls.select().where((cls.first.in_((first, second)))|(cls.second.in_((first, second)))).execute().all():
            return False
        return cls.create(first=first, second=second)

    @classmethod
    @logger.catch
    def delete_pair(cls, token_id: int) -> bool:
        """FIXME delete pair related tokens from table
            arguments:
                token_id: int
        """
        return cls.delete().where((cls.first == token_id)|(cls.second == token_id)).execute()

    @classmethod
    @logger.catch
    def remove_pairs_from_list(cls, token_list: list) -> bool:
        """remove  pairs from the list
            arguments:
                token_list: list
        """
        return cls.delete().where((cls.first.in_(token_list))|(cls.second.in_(token_list))).execute()

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
        first = cls.select(cls.first.alias('token'))
        second = cls.select(cls.second.alias('token'))
        query = first | second

        return tuple([value.token for value in query.execute()])


class Proxy(BaseModel):
    """
    class for a table proxies
        Methods:
            add_proxy
            delete_proxy
            TODO Clear table ???
            get_list_proxies
            get_low_used_proxy
        fields:
            proxy: str
            quantity users ????
    """
    proxy = CharField(max_length=100, unique=True, verbose_name='Адрес прокси с портом.')
    using = IntegerField(default=0, verbose_name='Количество пользователей.')

    @classmethod
    @logger.catch
    def add_proxy(cls, proxy: str) -> bool:
        res = cls.get_or_none(proxy=proxy)
        return False if res else cls.create(proxy=proxy)

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
    def get_low_used_proxy(cls: 'Proxy') -> tuple:
        """return Tuple[str, int] or ()
         TODO add to the set_proxy method in "model User" counting the number of users
         """
        result = cls.select(fn.MIN(cls.using)).scalar()
        if result:
            return result.proxy, result.using


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
        db.create_tables([User, UserTokenDiscord, TokenPair], safe=True)
        logger.info('DB REcreated')


def create_db() -> None:
    """Creates new tables in database. Drop all data from DB if it exists."""

    with db:
        db.create_tables([Proxy], safe=True)


if __name__ == '__main__':
    recreate = 0
    add_test_users = 0
    add_admins = 0
    add_tokens = 0
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
        for admin_id in admins_list:
            nick_name = "Admin"
            User.add_new_user(nick_name=nick_name, telegram_id=admin_id, proxy=DEFAULT_PROXY)
            User.set_user_status_admin(telegram_id=admin_id)
            User.activate_user(admin_id)
            logger.info(f"User {nick_name} with id {admin_id} created as ADMIN.")
