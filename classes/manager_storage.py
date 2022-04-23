from classes.discord_manager import DiscordTokenManager
from config import logger


class InstancesStorage:
    """
    Класс для хранения экземпляров классов данных (ID сообщения в дискорде, время и прочая)
    для каждого пользователя телеграма.
    Инициализируется при запуске бота.
    """

    _INSTANCES: dict = {}

    @classmethod
    @logger.catch
    async def get_instance(cls, telegram_id: str) -> 'DiscordTokenManager':
        """Возвращает текущий экземпляр класса для пользователя'"""

        return cls._INSTANCES.get(telegram_id)

    @classmethod
    @logger.catch
    async def add_or_update(cls, telegram_id: str, data: 'DiscordTokenManager') -> None:
        """Сохраняет экземпляр класса пользователя"""

        cls._INSTANCES.update(
            {
                telegram_id: data
            }
        )

    @classmethod
    @logger.catch
    async def mute(cls, telegram_id):
        user_class: 'DiscordTokenManager' = await cls.get_instance(telegram_id=telegram_id)
        if user_class:
            user_class.silence = True
            return True

    @classmethod
    @logger.catch
    async def unmute(cls, telegram_id):
        user_class: 'DiscordTokenManager' = await cls.get_instance(telegram_id=telegram_id)
        if user_class:
            user_class.silence = False
            return True

    @classmethod
    @logger.catch
    async def stop_work(cls, telegram_id: str):
        user_class: 'DiscordTokenManager' = await cls.get_instance(telegram_id=telegram_id)
        if user_class:
            user_class.working = False
