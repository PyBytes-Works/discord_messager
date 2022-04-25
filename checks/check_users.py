from aiogram.types import Message
from models import User
from config import admins_list


def is_admin(message: Message) -> bool:
    return User.is_admin(message.from_user.id)


def is_super_admin(message: Message) -> bool:
    return message.from_user.id in admins_list


def is_expired(message: Message):
    return User.is_user_expired(telegram_id=message.from_user.id)
