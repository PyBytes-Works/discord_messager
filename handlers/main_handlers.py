"""Модуль с основными обработчиками команд, сообщений и коллбэков"""
import aiogram.utils.exceptions
from aiogram.dispatcher.filters import Text
from aiogram.types import Message, CallbackQuery
from aiogram.dispatcher import FSMContext

from classes.instances_storage import InstancesStorage
from classes.replies import RepliesManager
from config import logger, Dispatcher, VERSION, bot
from keyboards import user_menu_keyboard, in_work_keyboard
from classes.discord_manager import DiscordManager
from classes.db_interface import DBI
from states import UserStates


@logger.catch
async def start_parsing_command_handler(message: Message, state: FSMContext) -> None:
    """Получает случайное сообщение из дискорда, ставит машину состояний в положение
    'жду ответа пользователя'
    Обработчик нажатия на кнопку "Старт"
    """

    user_telegram_id: str = str(message.from_user.id)
    user_is_active: bool = await DBI.user_is_active(telegram_id=user_telegram_id)
    user_expired: bool = await DBI.is_expired_user_deactivated(message)
    if not user_is_active or user_expired:
        return
    if not await DBI.get_all_user_tokens(user_telegram_id):
        await message.answer("Сначала добавьте пару токенов.", reply_markup=user_menu_keyboard())
        return
    if await DBI.is_user_work(telegram_id=user_telegram_id):
        await DBI.set_user_is_not_work(telegram_id=user_telegram_id)
        await state.finish()
    await message.answer("Запускаю бота", reply_markup=in_work_keyboard())
    await DBI.set_user_is_work(telegram_id=user_telegram_id)
    await UserStates.in_work.set()
    manager: 'DiscordManager' = await InstancesStorage.get_or_create_instance(message=message)
    await manager.lets_play()
    await DBI.set_user_is_not_work(telegram_id=user_telegram_id)
    await message.answer("Закончил работу.", reply_markup=user_menu_keyboard())
    await state.finish()


@logger.catch
async def answer_to_reply_handler(callback: CallbackQuery, state: FSMContext):
    """Запрашивает текст ответа на реплай для отправки в дискорд"""

    message_id: str = callback.data.rsplit("_", maxsplit=1)[-1]
    try:
        await bot.delete_message(callback.message.chat.id, callback.message.message_id)
        await callback.message.answer('Введите текст ответа:')
        await state.update_data(message_id=message_id)
        await callback.answer()
    except aiogram.utils.exceptions.MessageToDeleteNotFound:
        logger.warning("Не нашел сообщение для удаления.")
        await state.finish()
    except aiogram.utils.exceptions.InvalidQueryID:
        logger.warning("Сообщение просрочено.")
        await state.finish()


@logger.catch
async def send_message_to_reply_handler(message: Message, state: FSMContext):
    """Отправляет сообщение в дискорд реплаем на реплай"""

    state_data: dict = await state.get_data()
    message_id: str = state_data.get("message_id")
    user_telegram_id: str = str(message.from_user.id)
    if not await RepliesManager(user_telegram_id).update_text(
            message_id=message_id, text=message.text):
        logger.warning("f: send_message_to_reply_handler: elem in Redis data not found or timeout error")
        await message.answer('Время хранения данных истекло.')
        return
    await message.answer('Добавляю сообщение в очередь. Это займет несколько секунд.')
    await message.answer('Сообщение добавлено в очередь сообщений.')


@logger.catch
async def default_message(message: Message) -> None:
    """Ответ на любое необработанное действие активного пользователя."""

    user_telegram_id: str = str(message.from_user.id)
    is_user_exists: bool = await DBI.get_user_by_telegram_id(telegram_id=user_telegram_id)
    if is_user_exists:
        if not await DBI.is_expired_user_deactivated(message):
            await message.answer(f'Текущая версия: {VERSION}', reply_markup=user_menu_keyboard())


@logger.catch
async def activate_valid_user_handler(message: Message):
    """Активирует пользователя если он продлил оплату при команде /start"""

    user_telegram_id: str = str(message.from_user.id)
    is_user_exists: bool = await DBI.get_user_by_telegram_id(telegram_id=user_telegram_id)
    is_subscribe_active: bool = await DBI.is_subscribe_active(telegram_id=user_telegram_id)
    is_user_active: bool = await DBI.user_is_active(telegram_id=user_telegram_id)
    if is_user_exists and is_subscribe_active and not is_user_active:
        await DBI.activate_user(telegram_id=user_telegram_id)
        await message.answer("Аккаунт активирован.")


@logger.catch
async def autoanswer_enabled_handler(message: Message):
    """Включает автоответчик ИИ"""

    manager: 'DiscordManager' = await InstancesStorage.switch_autoanswer(message)
    if manager.auto_answer:
        await message.answer("Автоответчик включен.", reply_markup=in_work_keyboard())
    else:
        await message.answer("Автоответчик вЫключен.", reply_markup=in_work_keyboard())


@logger.catch
async def silence_mode_handler(message: Message):
    """Включает тихий режим"""

    await InstancesStorage.mute(message)
    await message.answer("Тихий режим включен.", reply_markup=in_work_keyboard())


@logger.catch
def register_handlers(dp: Dispatcher) -> None:
    """
    Регистратор для функций данного модуля
    """

    dp.register_message_handler(activate_valid_user_handler, commands=["start"])
    dp.register_message_handler(autoanswer_enabled_handler, Text(equals=["Автоответчик ВКЛ", "Автоответчик ВЫКЛ"]), state=UserStates.in_work)
    dp.register_message_handler(silence_mode_handler, Text(equals=["Тихий режим (mute)"]), state=UserStates.in_work)

    dp.register_message_handler(start_parsing_command_handler, Text(equals=["Старт",
                                                                            "Старт & Mute", "Автоответчик"]))
    dp.register_callback_query_handler(answer_to_reply_handler, Text(startswith=[
        "reply_"]), state=UserStates.in_work)
    dp.register_message_handler(send_message_to_reply_handler, state=UserStates.in_work)
    dp.register_message_handler(default_message)
