from functools import wraps
from typing import Callable, Any

from aiogram.types import Message

from checks.check_users import is_admin, is_super_admin, is_user_subscribe_active
from classes.db_interface import DBI
from config import logger, admins_list


@logger.catch
def check_is_super_admin(func: Callable) -> Callable:
    """decorator for handler check user on super admin"""

    @wraps(func)
    async def wrapper(*args, **kwargs) -> Any:
        message: Message = args[0]
        telegram_id: str = str(message.from_user.id)
        if await DBI.is_superadmin(telegram_id=telegram_id):
            logger.debug(f"User {message.from_user.id} is superadmin.")
            return await func(*args, **kwargs)
        logger.debug(f"User {message.from_user.id} is not superadmin.")

    return wrapper


@logger.catch
def check_is_admin(func: Callable) -> Callable:
    """decorator for handler check user on admin and super admin"""

    @wraps(func)
    async def wrapper(*args, **kwargs) -> Any:
        message: Message = args[0]
        telegram_id: str = str(message.from_user.id)
        user_is_admin: bool = await DBI.is_admin(telegram_id=telegram_id)
        if user_is_admin:
            logger.debug(f"User {message.from_user.id} is admin.")
            return await func(*args, **kwargs)
        logger.warning(f"User {message.from_user.id} is not admin.")

    return wrapper


# class CheckAccess:
#     """class with decorators access"""
#
#     def __init__(self, func: Callable) -> None:
#         self.func = func
#
#     def __call__(self, *args, **kwargs):
#         return self.func(*args, **kwargs)
#
#     @classmethod
#     @logger.catch
#     def check_expired(cls, func: Callable) -> Callable:
#         """decorator for handler check expired for user"""
#
#         @wraps(func)
#         async def wrapper(*args, **kwargs) -> Any:
#             message: Message = args[0]
#             if is_user_subscribe_active(telegram_id=message.from_user.id):
#                 return await func(*args, **kwargs)
#             logger.warning(f"User {message.from_user.id} expired.")
#         return wrapper
#
#     @classmethod
#     @logger.catch
#     def check_admin(cls, func: Callable) -> Callable:
#         """decorator for handler check user on admin and super admin"""
#
#         @wraps(func)
#         async def wrapper(*args, **kwargs) -> Any:
#             message: Message = args[0]
#             telegram_id = message.from_user.id
#             if is_admin(telegram_id=str(telegram_id)) or is_super_admin(telegram_id=str(telegram_id)):
#                 return await func(*args, **kwargs)
#             logger.warning(f"User {message.from_user.id} is not admin.")
#
#         return wrapper
#
#     @classmethod
#     @logger.catch
#     def check_super_admin(cls, func: Callable) -> Callable:
#         """decorator for handler check user on super admin"""
#
#         @wraps(func)
#         async def wrapper(*args, **kwargs) -> Any:
#             message: Message = args[0]
#             telegram_id = message.from_user.id
#             if is_admin(args[0]) or is_super_admin(telegram_id=str(telegram_id)):
#                 return await func(*args, **kwargs)
#             logger.warning(f"User {message.from_user.id} is not superadmin.")
#
#         return wrapper
