from functools import wraps
from typing import Callable, Any

from aiogram.types import Message

from checks.check_users import is_admin, is_super_admin, is_user_subscribe_active
from config import logger


class CheckAccess:
    """class with decorators access"""

    def __init__(self, func: Callable) -> None:
        self.func = func

    def __call__(self, *args, **kwargs):
        return self.func(*args, **kwargs)

    @classmethod
    @logger.catch
    def check_expired(cls, func: Callable) -> Callable:
        """decorator for handler check expired for user"""

        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            message: Message = args[0]
            if is_user_subscribe_active(telegram_id=message.from_user.id):
                return await func(*args, **kwargs)

        return wrapper

    @classmethod
    @logger.catch
    def check_admin(cls, func: Callable) -> Callable:
        """decorator for handler check user on admin and super admin"""

        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            message: Message = args[0]
            telegram_id = message.from_user.id
            if is_admin(telegram_id=str(telegram_id)) or is_super_admin(telegram_id=str(telegram_id)):
                return await func(*args, **kwargs)

        return wrapper

    @classmethod
    @logger.catch
    def check_super_admin(cls, func: Callable) -> Callable:
        """decorator for handler check user on super admin"""

        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            message: Message = args[0]
            telegram_id = message.from_user.id
            if is_admin(args[0]) or is_super_admin(telegram_id=str(telegram_id)):
                return await func(*args, **kwargs)

        return wrapper
