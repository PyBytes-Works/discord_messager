import random
from typing import List, Tuple, Dict
from collections import namedtuple

from aiogram.types import ReplyKeyboardRemove, Message

from models import User, Token, Proxy, UserChannel
from config import logger, admins_list
from checks import check_users


class DBI:
    """Database interface class"""

    @classmethod
    @logger.catch
    async def is_expired_user_deactivated(cls, message: Message) -> bool:
        """Удаляет пользователя с истекшим сроком действия.
        Возвращает True если деактивирован."""

        telegram_id: str = str(message.from_user.id)
        subscribe_active: bool = await cls.is_subscribe_active(telegram_id)
        user_is_admin: bool = await cls.is_admin(telegram_id)
        user_is_superadmin: bool = telegram_id in admins_list
        if not subscribe_active and not user_is_admin and not user_is_superadmin:
            await message.answer(
                "Время подписки истекло. Ваш аккаунт деактивирован, токены удалены.",
                reply_markup=ReplyKeyboardRemove()
            )
            await cls.deactivate_user(telegram_id)
            text = (
                f"Время подписки {telegram_id} истекло, "
                f"пользователь декативирован, его токены удалены"
            )
            logger.info(text)
            return True

        return False

    @classmethod
    @logger.catch
    async def form_new_tokens_pairs(cls, telegram_id: str) -> None:
        """Формирует пары токенов из свободных"""

        free_tokens: Tuple[List[namedtuple], ...] = await DBI.get_all_free_tokens(telegram_id)
        formed_pairs: int = 0
        sorted_tokens: Tuple[List[namedtuple], ...] = tuple(
            sorted(
                array, key=lambda x: x.last_message_time, reverse=True
            )
            for array in free_tokens
        )
        logger.debug(f"\n\tAll free tokens: {free_tokens}")
        for tokens in sorted_tokens:
            while len(tokens) > 1:
                random.shuffle(tokens)
                first_token = tokens.pop()
                second_token = tokens.pop()
                logger.debug(f"\n\tPaired tokens: {first_token} + {second_token}")
                formed_pairs += await DBI.make_tokens_pair(first_token.token_pk, second_token.token_pk)

    @classmethod
    @logger.catch
    async def add_new_user(
            cls, nick_name: str, telegram_id: str, proxy_pk: int, expiration: int, max_tokens: int
    ) -> bool:
        return User.add_new_user(
            nick_name=nick_name, telegram_id=telegram_id, proxy_pk=proxy_pk, expiration=expiration,
            max_tokens=max_tokens)

    @classmethod
    @logger.catch
    async def get_active_users(cls) -> List[str]:
        return User.get_active_users()

    @classmethod
    @logger.catch
    async def get_working_users(cls) -> List[str]:
        return User.get_working_users()

    @classmethod
    @logger.catch
    async def get_all_users(cls) -> Tuple[namedtuple]:
        return User.get_all_users()

    @classmethod
    @logger.catch
    async def set_user_status_admin(cls, telegram_id: str) -> bool:
        return User.set_user_status_admin(telegram_id=telegram_id)

    @classmethod
    @logger.catch
    async def delete_proxy_for_all_users(cls) -> int:
        return User.delete_proxy_for_all_users()

    @classmethod
    @logger.catch
    async def set_new_proxy_for_all_users(cls) -> int:
        return User.set_new_proxy_for_all_users()

    @classmethod
    @logger.catch
    async def activate_user(cls, telegram_id: str) -> bool:
        return User.activate_user(telegram_id=telegram_id)

    @classmethod
    @logger.catch
    async def deactivate_user(cls, telegram_id: str) -> bool:
        return User.deactivate_user(telegram_id=telegram_id)

    @classmethod
    @logger.catch
    async def is_user_work(cls, telegram_id: str) -> bool:
        return User.get_is_work(telegram_id=telegram_id)

    @classmethod
    @logger.catch
    async def is_admin(cls, telegram_id: str) -> bool:
        return User.is_admin(telegram_id=telegram_id)

    @classmethod
    @logger.catch
    async def get_expiration_date(cls, telegram_id: str) -> int:
        return User.get_expiration_date(telegram_id=telegram_id)

    @classmethod
    @logger.catch
    async def get_user_by_telegram_id(cls, telegram_id: str) -> 'User':
        return User.get_user_by_telegram_id(telegram_id=telegram_id)

    @classmethod
    @logger.catch
    async def get_all_inactive_users(cls) -> Dict[str, 'User']:
        return User.get_all_inactive_users()

    @classmethod
    @logger.catch
    async def is_subscribe_active(cls, telegram_id: str) -> bool:
        """
        Возвращает статус подписки пользователя,

        False если срок подписки истек

        True если подписка действует
        """
        return User.is_subscribe_active(telegram_id=telegram_id)

    @classmethod
    @logger.catch
    async def user_is_active(cls, telegram_id: str) -> bool:
        return User.is_active(telegram_id=telegram_id)

    @classmethod
    @logger.catch
    async def set_user_is_work(cls, telegram_id: str) -> bool:
        return User.set_user_is_work(telegram_id=telegram_id)

    @classmethod
    @logger.catch
    async def set_max_tokens(cls, telegram_id: str, max_tokens: int) -> bool:
        return User.set_max_tokens(telegram_id=telegram_id, max_tokens=max_tokens)

    @classmethod
    @logger.catch
    async def set_expiration_date(cls, telegram_id: str, subscription_period: int) -> bool:
        return User.set_expiration_date(
            telegram_id=telegram_id, subscription_period=subscription_period)

    @classmethod
    @logger.catch
    async def set_user_is_not_work(cls, telegram_id: str) -> bool:
        return User.set_user_is_not_work(telegram_id=telegram_id)

    @classmethod
    @logger.catch
    async def delete_all_pairs(cls, telegram_id: str) -> bool:
        return User.delete_all_pairs(telegram_id=telegram_id)

    @classmethod
    @logger.catch
    async def delete_user_by_telegram_id(cls, telegram_id: str) -> bool:
        return User.delete_user_by_telegram_id(telegram_id=telegram_id)

    @classmethod
    @logger.catch
    async def get_user_proxy(cls, telegram_id: str) -> str:
        return User.get_proxy(telegram_id=telegram_id)

    @classmethod
    @logger.catch
    async def get_last_message_time(cls, token: str) -> int:
        return Token.get_last_message_time(token=token)

    @classmethod
    @logger.catch
    async def is_token_exists(cls, token: str) -> bool:
        return Token.is_token_exists(token)

    @classmethod
    @logger.catch
    async def get_all_related_user_tokens(cls, telegram_id: str) -> List[namedtuple]:
        """
        Возвращает список всех связанных ТОКЕНОВ пользователя по его telegram_id:
        return: list of named tuples
        list of namedtuple fields:
            token str
            cooldown  int
            last_message_time Timestamp
        """

        return Token.get_related_tokens(telegram_id=telegram_id)

    @classmethod
    @logger.catch
    async def get_all_user_tokens(cls, telegram_id: str) -> int:
        return Token.get_all_user_tokens(telegram_id=telegram_id)

    @classmethod
    @logger.catch
    async def delete_token(cls, token: str) -> int:
        return Token.delete_token(token=token)

    @classmethod
    @logger.catch
    async def delete_token_by_pk(cls, token_pk: int):
        return Token.delete_token_by_id(token_pk=token_pk)

    @classmethod
    @logger.catch
    async def update_token_last_message_time(cls, token: str) -> bool:
        return Token.update_token_last_message_time(token=token)

    @classmethod
    @logger.catch
    async def get_all_tokens_info(cls, telegram_id: str) -> List[namedtuple]:
        return Token.get_all_tokens_info(telegram_id=telegram_id)

    @classmethod
    @logger.catch
    async def get_all_free_tokens(cls, telegram_id: str) -> Tuple[List[namedtuple], ...]:
        return Token.get_all_free_tokens(telegram_id=telegram_id)

    @classmethod
    @logger.catch
    async def get_all_discord_id(cls, telegram_id: str) -> List[str]:
        return Token.get_all_discord_id(telegram_id=telegram_id)

    @classmethod
    @logger.catch
    async def get_info_by_token(cls, token: str) -> 'namedtuple':
        return Token.get_token_info(token=token)

    @classmethod
    @logger.catch
    async def get_info_by_token_pk(cls, token_pk: int) -> 'namedtuple':
        return Token.get_token_info_by_token_pk(token_pk=token_pk)

    @classmethod
    @logger.catch
    async def set_token_name(cls, token_pk: int, name: str) -> int:
        return Token.set_token_name(token_pk=token_pk, name=name)

    @classmethod
    @logger.catch
    async def make_tokens_pair(cls, first_token, second_token) -> bool:
        return Token.make_tokens_pair(first_token, second_token)

    @classmethod
    @logger.catch
    async def get_number_of_free_slots_for_tokens(cls, telegram_id: str) -> int:
        """Todo вот убрать проверку и что возвращать?"""
        if (check_users.is_super_admin(telegram_id=telegram_id) or
                check_users.is_super_admin(telegram_id=telegram_id)):
            return 100
        return Token.get_number_of_free_slots_for_tokens(telegram_id)

    @classmethod
    @logger.catch
    async def check_token_by_discord_id(cls, discord_id: str):
        return Token.check_token_by_discord_id(discord_id=discord_id)

    @classmethod
    @logger.catch
    async def add_token_by_telegram_id(
            cls, telegram_id: str, token: str, discord_id: str, user_channel_pk: int) -> bool:
        return Token.add_token(
            telegram_id=telegram_id, token=token, discord_id=discord_id,
            user_channel_pk=user_channel_pk
        )

    @classmethod
    @logger.catch
    async def get_closest_token_time(cls, telegram_id: str) -> namedtuple:
        return Token.get_closest_token_time(telegram_id=telegram_id)

    @classmethod
    @logger.catch
    async def add_user_channel(cls, telegram_id: str, channel_id: int, guild_id: int,
                               name: str = '', cooldown: int = 60
                               ) -> int:
        return UserChannel.add_user_channel(
            telegram_id=telegram_id, channel_id=channel_id,
            guild_id=guild_id, name=name, cooldown=cooldown)

    @classmethod
    @logger.catch
    async def add_new_proxy(cls, proxy: str) -> bool:
        return Proxy.add_proxy(proxy=proxy)

    @classmethod
    @logger.catch
    async def delete_all_proxy(cls) -> bool:
        return Proxy.delete_all_proxy()

    @classmethod
    @logger.catch
    async def delete_proxy(cls, proxy: str) -> bool:
        return Proxy.delete_proxy(proxy=proxy)

    @classmethod
    @logger.catch
    async def get_proxy_count(cls) -> int:
        return Proxy.get_proxy_count()

    @classmethod
    @logger.catch
    async def get_low_used_proxy(cls) -> namedtuple:
        return Proxy.get_low_used_proxy()

    @classmethod
    @logger.catch
    async def update_proxies_for_owners(cls, proxy) -> int:
        Proxy.delete_proxy(proxy=proxy)
        return Proxy.set_proxy_if_not_exists()

    @classmethod
    @logger.catch
    async def update_user_channel_cooldown(cls, user_channel_pk: int, cooldown: int) -> int:
        return UserChannel.update_cooldown(user_channel_pk=user_channel_pk, cooldown=cooldown)

    @classmethod
    @logger.catch
    async def set_user_channel_name(cls, user_channel_pk: int, name: str) -> int:
        return UserChannel.set_user_channel_name(user_channel_pk=user_channel_pk, name=name)

    @classmethod
    @logger.catch
    async def get_user_channels(cls, telegram_id: str) -> List[namedtuple]:
        return UserChannel.get_user_channels_by_telegram_id(telegram_id=telegram_id)

    @classmethod
    @logger.catch
    async def get_channel(cls, user_channel_pk: int) -> namedtuple:
        return UserChannel.get_user_channel(user_channel_pk=user_channel_pk)
