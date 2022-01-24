"""Модуль с основными обработчиками команд, сообщений и коллбэков"""

from aiogram.dispatcher.filters import Text
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.dispatcher import FSMContext

from config import logger, Dispatcher, users_data_storage
from models import User
from keyboards import cancel_keyboard
from discord_handler import MessageReceiver, DataStore, MessageSender
from states import UserState


@logger.catch
async def cancel_handler(message: Message, state: FSMContext) -> None:
    """
    Отменяет текущие запросы и сбрасывает состояние.

    """
    logger.info(f'CANCELED')
    await state.finish()
    await message.answer("Ввод отменен.")


@logger.catch
async def start_command_handler(message: Message) -> None:
    """Получает случайное сообщение из дискорда"""

    await message.answer("Начинаю получение данных", reply_markup=cancel_keyboard())
    print("Создаю экземпляр класса-хранилища")
    new_store = DataStore(message.from_user.id)
    print("Добавляю его в общее хранилище")
    users_data_storage.add_instance(telegram_id=message.from_user.id, data=new_store)
    print("Отправляю запрос к АПИ")
    text = MessageReceiver.get_message(new_store)
    print("Получаю ответ", text)
    await message.answer(f"Данные получены:"
                         f"\nСообщение: {text}")
    await UserState.user_wait_message.set()


@logger.catch
async def send_to_discord(message: Message, state: FSMContext) -> None:
    """Отправляет полученное сообщение в дискорд"""
    text = message.text
    if len(text) > 50:
        await message.answer(
            "Сообщение не должно быть длиннее 50 символов. Попробуй еще раз.",
            reply_markup=cancel_keyboard()
        )
        return
    await message.answer("Понял, принял, отправляю.", reply_markup=cancel_keyboard())
    datastore = users_data_storage.get_instance(message.from_user.id)
    result = MessageSender.send_message(text=message.text, datastore=datastore)
    await message.answer(f"Результат отправки: {result}", reply_markup=ReplyKeyboardRemove())
    await state.finish()


@logger.catch
async def default_message(message: Message) -> None:
    """Ответ на любое необработанное действие активного пользователя."""

    if User.is_active(message.from_user.id):
        await message.answer(
            'Доступные команды\n'
            '/start - Активирует бота.'
        )


@logger.catch
def register_handlers(dp: Dispatcher) -> None:
    """
    Регистратор для функций данного модуля
    """
    dp.register_message_handler(
        cancel_handler, commands=['отмена', 'cancel'], state="*")
    dp.register_message_handler(
        cancel_handler, Text(startswith=["отмена", "cancel"], ignore_case=True), state="*")
    dp.register_message_handler(start_command_handler, commands=["start", "старт"])
    dp.register_message_handler(send_to_discord, state=UserState.user_wait_message)
    dp.register_message_handler(default_message)
