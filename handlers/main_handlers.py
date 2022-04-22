"""Модуль с основными обработчиками команд, сообщений и коллбэков"""

from typing import List

from aiogram.dispatcher.filters import Text
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.dispatcher import FSMContext

from config import logger, Dispatcher
from keyboards import cancel_keyboard, user_menu_keyboard
from classes.discord_manager import DiscordTokenManager
from states import UserStates
from classes.redis_interface import RedisDB
from classes.db_interface import DBI


@logger.catch
async def cancel_handler(message: Message, state: FSMContext) -> None:
    """
    Отменяет текущие запросы и сбрасывает состояние.
    Ставит пользователя в нерабочее состояние.
    Обработчик команды /cancel
    """

    user_telegram_id: str = str(message.from_user.id)
    text: str = ''
    keyboard = user_menu_keyboard
    if await DBI.is_user_work(telegram_id=user_telegram_id):
        text: str = "\nДождитесь завершения работы бота. Это займет несколько секунд..."
        keyboard = ReplyKeyboardRemove
    await message.answer(
        "Вы отменили текущую команду." + text, reply_markup=keyboard()
    )
    logger.debug(f"\n\t{user_telegram_id}: canceled command.")
    await DBI.set_user_is_not_work(telegram_id=user_telegram_id)
    await state.finish()


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
    await DBI.set_user_is_work(telegram_id=user_telegram_id)
    mute: bool = False
    mute_text: str = ''
    if message.text == "Старт & Mute":
        mute_text: str = "в тихом режиме."
        mute = True
    await message.answer("Запускаю бота " + mute_text, reply_markup=cancel_keyboard())
    await UserStates.in_work.set()
    await DiscordTokenManager(message=message, mute=mute).lets_play()
    await message.answer("Закончил работу.", reply_markup=user_menu_keyboard())
    await state.finish()


@logger.catch
async def answer_to_reply_handler(callback: CallbackQuery, state: FSMContext):
    """Запрашивает текст ответа на реплай для отправки в дискорд"""

    message_id: str = callback.data.rsplit("_", maxsplit=1)[-1]
    await callback.message.answer('Введите текст ответа:', reply_markup=cancel_keyboard())
    await state.update_data(message_id=message_id)
    await callback.answer()


@logger.catch
async def send_message_to_reply_handler(message: Message, state: FSMContext):
    """Отправляет сообщение в дискорд реплаем на реплай"""

    state_data: dict = await state.get_data()
    message_id: str = state_data.get("message_id")
    user_telegram_id: str = str(message.from_user.id)
    redis_data: List[dict] = await RedisDB(redis_key=user_telegram_id).load()
    for elem in redis_data:
        if str(elem.get("message_id")) == str(message_id):
            elem.update({"answer_text": message.text})
            break
    else:
        logger.warning("f: send_message_to_reply_handler: elem in Redis data not found.")
        await message.answer('Время хранения данных истекло.', reply_markup=cancel_keyboard())
        return
    await message.answer('Добавляю сообщение в очередь. Это займет несколько секунд.', reply_markup=ReplyKeyboardRemove())
    await RedisDB(redis_key=user_telegram_id).save(data=redis_data)
    await message.answer('Сообщение добавлено в очередь сообщений.', reply_markup=cancel_keyboard())


@logger.catch
async def default_message(message: Message) -> None:
    """Ответ на любое необработанное действие активного пользователя."""

    if await DBI.user_is_active(message.from_user.id):
        if await DBI.is_expired_user_deactivated(message):
            return
        await message.answer('Выберите команду.', reply_markup=user_menu_keyboard())


@logger.catch
async def activate_valid_user_handler(message: Message):
    """Активирует пользователя если он продлил оплату при команде /start"""

    user_telegram_id: str = str(message.from_user.id)
    user_not_expired: bool = await DBI.check_expiration_date(telegram_id=user_telegram_id)
    user_activated: bool = await DBI.user_is_active(telegram_id=user_telegram_id)
    if user_not_expired and not user_activated:
        await DBI.activate_user(telegram_id=user_telegram_id)
        await message.answer("Аккаунт активирован.")


@logger.catch
def register_handlers(dp: Dispatcher) -> None:
    """
    Регистратор для функций данного модуля
    """

    dp.register_message_handler(cancel_handler, commands=['отмена', 'cancel'], state="*")
    dp.register_message_handler(cancel_handler, Text(startswith=["отмена", "cancel"], ignore_case=True), state="*")
    dp.register_message_handler(activate_valid_user_handler, commands=["start"])
    dp.register_message_handler(start_parsing_command_handler, Text(equals=["Старт", "Старт & Mute"]))
    dp.register_callback_query_handler(answer_to_reply_handler, Text(startswith=["reply_"]), state=UserStates.in_work)
    dp.register_message_handler(send_message_to_reply_handler, state=UserStates.in_work)
    dp.register_message_handler(default_message)
