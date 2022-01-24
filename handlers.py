"""Модуль с основными обработчиками команд, сообщений и коллбэков"""

from aiogram.dispatcher.filters import Text
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.dispatcher import FSMContext

from config import logger, Dispatcher, bot, users_data_storage
from models import User, Filter, UserCollection, AllFilters
from keyboards import cancel_keyboard
from receiver import MessageReceiver, DataStore, MessageSender


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
    print("Bot started.")

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


@logger.catch
async def send_to_discord(message: Message) -> None:
    text = message.text[3:]
    print(text)
    await message.answer("Понял, принял, отправляю.", reply_markup=cancel_keyboard())
    datastore = users_data_storage.get_instance(message.from_user.id)
    result = MessageSender.send_message(text, datastore=datastore)
    await message.answer(f"Результат отправки: {result}")


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
    dp.register_message_handler(send_to_discord, commands=["s"])
    dp.register_message_handler(default_message)
