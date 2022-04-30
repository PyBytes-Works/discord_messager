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
    async def get_or_create_instance(
            cls, message: Message = None, telegram_id: str = '') -> 'DiscordManager':
        """Возвращает текущий экземпляр класса для пользователя'"""

        telegram_id: str = str(message.from_user.id) if message else telegram_id
        spam: 'DiscordManager' = cls._INSTANCES.get(telegram_id)
        if not spam and message:
            await cls._add_or_update(message)
        return cls._INSTANCES.get(telegram_id)

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
    async def stop_work(cls, telegram_id: str):

        user_class: 'DiscordManager' = await cls.get_or_create_instance(telegram_id=telegram_id)
        if user_class:
            user_class.is_working = False

    @classmethod
    @logger.catch
    async def reboot(cls, telegram_id: str):

        user_class: 'DiscordManager' = await cls.get_or_create_instance(telegram_id=telegram_id)
        if user_class:
            user_class.reboot = True

