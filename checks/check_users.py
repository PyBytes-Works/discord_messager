from models import User
from config import admins_list


def is_admin(telegram_id: str) -> bool:
    """check is admin"""
    return User.is_admin(telegram_id=telegram_id)


def is_super_admin(telegram_id: str) -> bool:
    """check is super admin"""
    return str(telegram_id) in admins_list


def is_user_subscribe_active(telegram_id: str):
    """check subscribe"""
    return User.is_subscribe_active(telegram_id=telegram_id)
