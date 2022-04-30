from aiogram.types import Message

from classes.discord_manager import DiscordManager
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
    async def get_or_create_instance(cls, message: Message = None) -> 'DiscordManager':
        """Возвращает текущий экземпляр класса для пользователя'"""

        spam: 'DiscordManager' = cls._INSTANCES.get(str(message.from_user.id))
        if not spam:
            await cls._add_or_update(message)
        return cls._INSTANCES.get(message)

    @classmethod
    @logger.catch
    async def _add_or_update(cls, message: Message) -> None:
        """Сохраняет экземпляр класса пользователя"""

        telegram_id: str = str(message.from_user.id)
        data: DiscordManager = DiscordManager(message)
        cls._INSTANCES.update(
            {
                telegram_id: data
            }
        )

    @classmethod
    @logger.catch
    async def mute(cls, message: Message):

        user_class: 'DiscordManager' = await cls.get_or_create_instance(message)
        if user_class:
            user_class.silence = True
            return True

    @classmethod
    @logger.catch
    async def unmute(cls, message: Message):

        user_class: 'DiscordManager' = await cls.get_or_create_instance(message)
        if user_class:
            user_class.silence = False
            return True

    @classmethod
    @logger.catch
    async def stop_work(cls, message: Message):

        user_class: 'DiscordManager' = await cls.get_or_create_instance(message)
        if user_class:
            user_class.is_working = False
            user_class.reboot = True
