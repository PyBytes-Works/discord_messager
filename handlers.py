"""Модуль с основными обработчиками команд, сообщений и коллбэков"""

from aiogram.dispatcher.filters import Text
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.dispatcher import FSMContext

from config import logger, Dispatcher, bot
from models import User, Filter, UserCollection, AllFilters
from keyboards import cancel_keyboard
from receiver import MessageReceiver


@logger.catch
async def cancel_handler(message: Message, state: FSMContext) -> None:
    """
    Отменяет текущие запросы и сбрасывает состояние.

    """
    logger.info(f'CANCELED')
    await state.finish()
    await message.answer("Ввод отменен.")


@logger.catch
async def start_command_handlder(message: Message) -> None:
    print("Bot started.")

    await message.answer("Начинаю получение данных", reply_markup=cancel_keyboard())
    text = MessageReceiver.get_message_data()
    await message.answer(f"Данные получены:"
                         f"\nСообщение: {text}")


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
    dp.register_message_handler(start_command_handlder, commands=["start", "старт"])
    dp.register_message_handler(default_message)
