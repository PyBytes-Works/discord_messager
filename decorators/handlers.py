from functools import wraps
from typing import Callable, Any

from checks.check_users import is_admin, is_super_admin, is_expired


class CheckAccess:
    """class with decorators access"""

    def __init__(self, func: Callable) -> None:
        self.func = func

    def __call__(self, *args, **kwargs):
        return self.func(*args, **kwargs)

    @classmethod
    def check_expired(cls, func: Callable) -> Callable:
        """decorator for handler check expired for user"""

        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            if is_expired(args[0]):
                return

            return await func(*args, **kwargs)

        return wrapper

    @classmethod
    def check_admin(cls, func: Callable) -> Callable:
        """decorator for handler check user on admin and super admin"""

        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            if is_admin(args[0]) or is_super_admin(args[0]):
                return await func(*args, **kwargs)

        return wrapper

    @classmethod
    def check_super_admin(cls, func: Callable) -> Callable:
        """decorator for handler check user on super admin"""

        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            if is_admin(args[0]) or is_super_admin(args[0]):
                return await func(*args, **kwargs)

        return wrapper
