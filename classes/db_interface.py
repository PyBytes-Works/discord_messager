from typing import List

from aiogram.types import ReplyKeyboardRemove, Message

from models import User, Token, Proxy
from classes.token_datastorage import TokenDataStore
from config import logger
from utils import send_report_to_admins


class DBI:

    """Database interface class"""

    def __init__(self, datastore: 'TokenDataStore' = None):
        self.datastore: 'TokenDataStore' = datastore

    @classmethod
    @logger.catch
    async def is_expired_user_deactivated(cls, message: Message) -> bool:
        """Удаляет пользователя с истекшим сроком действия.
        Возвращает True если деактивирован."""

        telegram_id: str = str(message.from_user.id)
        user_not_expired: bool = User.check_expiration_date(telegram_id)
        user_is_admin: bool = User.is_admin(telegram_id)
        if not user_not_expired and not user_is_admin:
            await message.answer(
                "Время подписки истекло. Ваш аккаунт деактивирован, токены удалены.",
                reply_markup=ReplyKeyboardRemove()
            )
            User.delete_all_tokens(telegram_id)
            User.deactivate_user(telegram_id)
            text = (
                f"Время подписки {telegram_id} истекло, "
                f"пользователь декативирован, его токены удалены"
            )
            logger.info(text)
            await send_report_to_admins(text)
            return True

        return False

    @classmethod
    @logger.catch
    async def add_new_user(cls, *args, **kwargs):
        return User.add_new_user(*args, **kwargs)

    @classmethod
    @logger.catch
    async def get_active_users(cls):
        return User.get_active_users()

    @classmethod
    @logger.catch
    async def get_working_users(cls):
        return User.get_working_users()

    @classmethod
    @logger.catch
    async def get_all_users(cls):
        return User.get_all_users()

    @classmethod
    @logger.catch
    async def set_user_status_admin(cls, telegram_id: str):
        return User.set_user_status_admin(telegram_id=telegram_id)

    @classmethod
    @logger.catch
    async def delete_proxy_for_all_users(cls):
        return User.delete_proxy_for_all_users()

    @classmethod
    @logger.catch
    async def set_new_proxy_for_all_users(cls):
        return User.set_new_proxy_for_all_users()

    @classmethod
    @logger.catch
    async def activate_user(cls, telegram_id: str):
        return User.activate_user(telegram_id=telegram_id)

    @classmethod
    @logger.catch
    async def is_active(cls, telegram_id: str) -> bool:
        return User.is_active(telegram_id=telegram_id)

    @classmethod
    @logger.catch
    async def deactivate_user(cls, telegram_id: str):
        return User.deactivate_user(telegram_id=telegram_id)

    @classmethod
    @logger.catch
    async def is_user_work(cls, telegram_id: str):
        return User.get_is_work(telegram_id=telegram_id)

    @classmethod
    @logger.catch
    async def is_admin(cls, telegram_id: str):
        return User.is_admin(telegram_id=telegram_id)

    @classmethod
    @logger.catch
    async def get_expiration_date(cls, telegram_id: str):
        return User.get_expiration_date(telegram_id=telegram_id)

    @classmethod
    @logger.catch
    async def get_user_by_telegram_id(cls, telegram_id: str) -> 'User':
        return User.get_user_by_telegram_id(telegram_id=telegram_id)

    @classmethod
    @logger.catch
    async def get_user_by_name(cls, name: str) -> 'User':
        # TODO написать метод в БД
        return User.get_or_none(User.nick_name.contains(name))

    @classmethod
    @logger.catch
    async def get_all_inactive_users(cls):
        return User.get_all_inactive_users()

    @classmethod
    @logger.catch
    async def check_expiration_date(cls, telegram_id: str):
        return User.check_expiration_date(telegram_id=telegram_id)

    @classmethod
    @logger.catch
    async def user_is_active(cls, telegram_id: str):
        return User.is_active(telegram_id=telegram_id)

    @classmethod
    @logger.catch
    async def set_user_is_work(cls, telegram_id: str):
        return User.set_user_is_work(telegram_id=telegram_id)

    @classmethod
    @logger.catch
    async def set_max_tokens(cls, telegram_id: str, max_tokens: int):
        return User.set_max_tokens(telegram_id=telegram_id, max_tokens=max_tokens)

    @classmethod
    @logger.catch
    async def set_expiration_date(cls, telegram_id: str, subscription_period: int):
        return User.set_expiration_date(telegram_id=telegram_id, subscription_period=subscription_period)

    @classmethod
    @logger.catch
    async def set_user_is_not_work(cls, telegram_id: str):
        return User.set_user_is_not_work(telegram_id=telegram_id)

    @classmethod
    @logger.catch
    async def delete_all_pairs(cls, telegram_id: str):
        return User.delete_all_pairs(telegram_id=telegram_id)

    @classmethod
    @logger.catch
    async def delete_user_by_telegram_id(cls, telegram_id: str):
        return User.delete_user_by_telegram_id(telegram_id=telegram_id)

    @classmethod
    @logger.catch
    async def get_proxy(cls, telegram_id: str):
        return User.get_proxy(telegram_id=telegram_id)

    @classmethod
    @logger.catch
    async def get_time_by_token(cls, token: str):
        return Token.get_time_by_token(token)

    @classmethod
    @logger.catch
    async def is_token_exists(cls, token: str):
        return Token.is_token_exists(token)

    @classmethod
    @logger.catch
    async def get_all_related_user_tokens(cls, telegram_id: str):
        return Token.get_all_related_user_tokens(telegram_id=telegram_id)

    @classmethod
    @logger.catch
    async def get_all_user_tokens(cls, telegram_id: str):
        return Token.get_all_user_tokens(telegram_id)

    @classmethod
    @logger.catch
    async def delete_token(cls, token: str):
        return Token.delete_token(token=token)

    @classmethod
    @logger.catch
    async def delete_token_by_id(cls, token_id: int):
        return Token.delete_token_by_id(token_id=token_id)

    @classmethod
    @logger.catch
    async def update_token_cooldown(cls, token: str, cooldown: int) -> bool:
        return Token.update_token_cooldown(token=token, cooldown=cooldown)

    @classmethod
    @logger.catch
    async def update_token_time(cls, token: str) -> bool:
        return Token.update_token_time(token=token)

    @classmethod
    @logger.catch
    async def update_mate_cooldown(cls, token: str, cooldown: int):
        return Token.update_mate_cooldown(token=token, cooldown=cooldown)

    @classmethod
    @logger.catch
    async def get_all_info_tokens(cls, telegram_id: str):
        return Token.get_all_info_tokens(telegram_id=telegram_id)

    @classmethod
    @logger.catch
    async def get_all_free_tokens(cls, telegram_id: str):
        return Token.get_all_free_tokens(telegram_id=telegram_id)

    @classmethod
    @logger.catch
    async def get_all_discord_id(cls, telegram_id: str) -> List[str]:
        # TODO Сделать метод - должен вернуть список дискорд_ид токенов для пользователя
        # return User.get_all_discord_id(telegram_id=telegram_id)
        return ['933119013775626302', '933119060420476939']

    @classmethod
    @logger.catch
    async def get_info_by_token(cls, token: str) -> dict:
        return Token.get_info_by_token(token=token)

    @classmethod
    @logger.catch
    async def make_tokens_pair(cls, first_token, second_token):
        return Token.make_tokens_pair(first_token, second_token)

    @classmethod
    @logger.catch
    async def get_number_of_free_slots_for_tokens(cls, telegram_id: str):
        return Token.get_number_of_free_slots_for_tokens(telegram_id)

    @classmethod
    @logger.catch
    async def check_token_by_discord_id(cls, discord_id: str):
        return Token.check_token_by_discord_id(discord_id=discord_id)

    @classmethod
    @logger.catch
    async def add_token_by_telegram_id(
            cls, telegram_id: str, token: str, discord_id: str, guild: int, channel: int, cooldown: int
    ) -> bool:
        return Token.add_token_by_telegram_id(
            telegram_id=telegram_id, token=token, discord_id=discord_id,
            guild=guild, channel=channel, cooldown=cooldown
        )

    @classmethod
    @logger.catch
    async def add_proxy(cls, proxy: str):
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
    async def get_low_used_proxy(cls) -> str:
        return Proxy.get_low_used_proxy()

    @classmethod
    @logger.catch
    async def update_proxies_for_owners(cls, proxy) -> int:
        return Proxy.update_proxies_for_owners(proxy=proxy)


if __name__ == '__main__':
    pass
