from aiogram.types import Message
from models import User
from config import admins_list


def is_admin(message: Message) -> bool:
    """check is admin"""
    return User.is_admin(message.from_user.id)


def is_super_admin(message: Message) -> bool:
    """check is super admin"""
    return str(message.from_user.id) in admins_list


def is_user_subscribe_active(message: Message):
    """check subscribe"""
    return User.is_subscribe_active(telegram_id=message.from_user.id)
