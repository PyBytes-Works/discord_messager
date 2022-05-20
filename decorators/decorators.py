from config import logger


def check_working(func):
    async def wrapper(*args, **kwargs):
        name: str = func.__name__
        if args and hasattr(args[0].__class__, name):
            is_working: bool = getattr(args[0], "is_working")
            if is_working:
                # logger.debug(f"\t{name}: OK")
                return await func(*args, **kwargs)
        logger.info(f"Work stopped: Method: {name}: FAIL")
        return

    return wrapper


def info_logger(func):
    async def wrapper(*args, **kwargs):
        name: str = func.__name__
        if args and hasattr(args[0].__class__, name):
            username: str = getattr(args[0], "_username")
            telegram_id: str = getattr(args[0], "_telegram_id")
            logger.info(f"Function: {name}: USER: {username}: {telegram_id} - begin.")
            spam = await func(*args, **kwargs)
            logger.info(f"Function: {name}: USER: {username}: {telegram_id} - over.")
            return spam
        return await func(*args, **kwargs)

    return wrapper
