from aiogram.types import Message

from classes.discord_manager import DiscordManager
from classes.keyboards_classes import MailerInWorkMenu
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
    async def switch_mute(cls, message: Message) -> None:

        user_class: 'DiscordManager' = await cls.get_or_create_instance(message)
        if user_class:
            text: str = "Тихий режим включен."
            if user_class.silence:
                user_class.silence = False
                text: str = "Тихий режим вЫключен."
            else:
                user_class.silence = True
            await message.answer(text, reply_markup=MailerInWorkMenu.keyboard())

    @classmethod
    @logger.catch
    async def switch_autoanswer(cls, message: Message):

        user_class: 'DiscordManager' = await cls.get_or_create_instance(message)
        if user_class:
            text: str = "Автоответчик включен."
            if user_class.auto_answer:
                text: str = "Автоответчик вЫключен."
                user_class.auto_answer = False
            else:
                user_class.auto_answer = True
            await message.answer(text, reply_markup=MailerInWorkMenu.keyboard())

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

