"""Модуль с основными обработчиками команд, сообщений и коллбэков"""
import re
from aiogram.dispatcher.filters import Text
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.dispatcher import FSMContext

from config import logger, Dispatcher, DEFAULT_PROXY
from models import User, UserTokenDiscord
from keyboards import cancel_keyboard, user_menu_keyboard
from discord_handler import MessageReceiver, DataStore, MessageSender, users_data_storage
from states import UserState
from utils import check_is_int


@logger.catch
async def cancel_handler(message: Message, state: FSMContext) -> None:
    """
    Отменяет текущие запросы и сбрасывает состояние.
    Ставит пользователя в нерабочее состояние.
    """
    user = message.from_user.id
    logger.info(f'CANCELED')
    await state.finish()
    await message.answer("Ввод отменен.", reply_markup=user_menu_keyboard())
    User.set_user_is_not_work(user)


# @logger.catch
# async def set_self_token_cooldown_handler(message: Message, state: FSMContext) -> None:
#     """Обработчик команды /set_cooldown"""
#
#     user_telegram_id = message.from_user.id
#     if User.is_active(telegram_id=user_telegram_id):
#         await message.answer("Введите время кулдауна в минутах", reply_markup=cancel_keyboard())
#         await UserState.set_user_self_cooldown.set()


@logger.catch
async def invitation_add_discord_token_handler(message: Message) -> None:
    """Запрос discord-токена """
    # print(message.from_user.id)
    user = message.from_user.id
    if User.is_active(telegram_id=user):
        if UserTokenDiscord.get_number_of_free_slots_for_tokens(user):
            await message.answer("Введите discord-токен", reply_markup=cancel_keyboard())
            await UserState.user_add_token.set()
            return
        await message.answer(
            "Максимальное количество discord-токенов уже добавлено", reply_markup=user_menu_keyboard())


@logger.catch
async def add_discord_token_handler(message: Message, state: FSMContext) -> None:
    """ Получение токена запрос ссылки на канал"""

    token = message.text
    await state.update_data(token=token)
    await message.answer(
        "Введите ссылку на канал в виде: https://discord.com/channels/932034587264167975/932034858906401842",
        reply_markup=cancel_keyboard()
    )
    await UserState.user_add_channel.set()


@logger.catch
async def add_channel_handler(message: Message, state: FSMContext) -> None:
    """
        получения ссылки на канал, запрос discord_id
    """
    mess = message.text
    guild, channel = mess.rsplit('/', maxsplit=3)[-2:]
    guild = check_is_int(guild)
    channel = check_is_int(channel)
    if not guild or not channel:
        await message.answer(
            "Проверьте ссылку на канал и попробуйте ещё раз", reply_markup=cancel_keyboard())
        return

    await state.update_data(guild=guild, channel=channel)
    await message.answer(
        "введите discord_id", reply_markup=cancel_keyboard())
    await UserState.user_add_discord_id.set()


# @logger.catch
# async def add_proxy_handler(message: Message, state: FSMContext) -> None:
#     """
#         добавить прокси
#     """
#
#     proxy = message.text
#     proxy = re.match(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,6}\b', proxy.strip())
#     if not proxy:
#         await message.answer(
#             "Проверьте proxy и попробуйте ещё раз", reply_markup=cancel_keyboard())
#         return
#
#     await state.update_data(proxy=proxy.string)
#     await message.answer(
#         "Добавьте language ru, es, en или другой)", reply_markup=cancel_keyboard())
#     await UserState.user_add_language.set()

@logger.catch
async def add_discord_id_handler(message: Message, state: FSMContext) -> None:
    """
        добавить discord_id
    """

    discord_id = message.text
    token = UserTokenDiscord.get_token_by_discord_id(discord_id)
    if not discord_id or token:
        await message.answer(
            "Проверьте discord_id и попробуйте ещё раз", reply_markup=cancel_keyboard())
        return

    await state.update_data(discord_id=discord_id)
    await message.answer(
        "Выберите основной язык канала: ru, es, en или другой)", reply_markup=cancel_keyboard())
    await UserState.user_add_language.set()


@logger.catch
async def add_language_handler(message: Message, state: FSMContext) -> None:
    """
       проверка и запись, либо возврат в другое состояние
    """

    languages = ['az', 'sq', 'am', 'en', 'ar', 'hy', 'af', 'eu', 'ba', 'be', 'bn', 'my', 'bg',
                 'bs', 'cy', 'hu', 'vi', 'ht', 'gl', 'nl', 'el', 'ka', 'gu', 'da', 'he', 'yi',
                 'id', 'ga', 'it', 'is', 'es', 'kk', 'kn', 'ca', 'ky', 'zh', 'ko', 'xh', 'km',
                 'lo', 'la', 'lv', 'lt', 'lb', 'mg', 'ms', 'ml', 'mt', 'mk', 'mi', 'mr', 'mn',
                 'de', 'ne', 'no', 'pa', 'fa', 'pl', 'pt', 'ro', 'ru', 'sr', 'si', 'sk', 'sl',
                 'sw', 'su', 'tg', 'th', 'tl', 'ta', 'tt', 'te', 'tr', 'uz', 'uk', 'ur', 'fi',
                 'fr', 'hi', 'hr', 'cs', 'sv', 'gd', 'et', 'eo', 'jv', 'ja']

    user = message.from_user.id
    language = message.text
    if language not in languages:
        await message.answer(
            "Язык не поддерживается попробуйте ещё раз ввести язык language ru, es, en или другой)",
            reply_markup=cancel_keyboard())
        return
    data = await state.get_data()

    token = data.get('token')
    guild = data.get('guild')
    discord_id = data.get('discord_id')
    channel = data.get('channel')
    proxy = DEFAULT_PROXY

    result = await DataStore.check_user_data(token, proxy, channel)
    if result.get('token') == 'bad token':
        await message.answer(
            "Ваш токен не прошел проверку в данном канале. "
            "\nЛибо канал не существует либо токен отсутствует данном канале, либо токен не рабочий.",
            reply_markup=cancel_keyboard()
        )
        await UserState.user_add_token.set()
        return
    # if result.get('proxy', 'bad proxy') == 'bad proxy':
    #     await message.answer(
    #                             "токен не добавлен повторите ввод proxy",
    #                             reply_markup=user_menu_keyboard())
        # await UserState.user_add_proxy.set()
        # return

    token = UserTokenDiscord.add_or_update_token_by_telegram_id(user, discord_id, token, proxy, guild, channel, language)
    if token:
        await message.answer(
                "Токен добавлен",
                reply_markup=user_menu_keyboard())
    else:
        await message.answer(
            "что то прошло не так, токен не добавлен",
            reply_markup=user_menu_keyboard())
    await state.finish()

#
# @logger.catch
# async def add_proxy_handler(message: Message) -> None:
#     """
#         get info
#     """
#     if User.is_active(message.from_user.id):
#
#         user = message.from_user.id
#         tokens = UserTokenDiscord.get_all_user_tokens(user)
#         if tokens:
#             token = UserTokenDiscord.get_info_by_token(tokens[0][[0].items()])
#             mess = (f'токен{token.get("token")} канал {token.get("channel")} гильдия '
#                     f'{token.get("guild")} colldown {token.get("colldown")}language{token.get("language")}')
#             await message.answer(
#                 "mess", reply_markup=user_menu_keyboard())
#
#         await message.answer(
#                 "Не обнаружено токенов", reply_markup=user_menu_keyboard())


@logger.catch
async def info_tokens_handler(message: Message, state: FSMContext) -> None:
    """выводит инфо о токенах
    TODO нужны тесты
    """
    user = message.from_user.id
    if User.is_active(message.from_user.id):
        data = UserTokenDiscord.get_all_info_tokens(user)
        print(data)
        for token_info in data:
            token = token_info.get('token')
            channel = token_info.get('channel')
            discord_id = token_info.get('discord_id')
            mate_id = token_info.get('mate_id')
            cooldown = token_info.get('cooldown')
            await message.answer(
                f"токен {token} канал {channel} дискорд id {discord_id} id пары  {mate_id} куллдаун {cooldown}",
                reply_markup=user_menu_keyboard()
            )


@logger.catch
async def start_command_handler(message: Message, state: FSMContext) -> None:
    """Получает случайное сообщение из дискорда, ставит машину состояний в положение
    'жду ответа пользователя'

    """
    user_telegram_id = message.from_user.id
    if not User.is_active(telegram_id=user_telegram_id):
        return
    if not UserTokenDiscord.get_all_user_tokens(user_telegram_id):
        await message.answer("Сначала добавьте токен.", reply_markup=user_menu_keyboard())
        await state.finish()
        return
    if not User.check_expiration_date(telegram_id=user_telegram_id):
        await message.answer("Время подписки истекло.", reply_markup=cancel_keyboard())
        User.deactivate_user(telegram_id=user_telegram_id)
        await state.finish()
        return
    await message.answer("Начинаю получение данных", reply_markup=cancel_keyboard())
    print("Создаю экземпляр класса-хранилища")
    new_store = DataStore(user_telegram_id)
    print("Добавляю его в общее хранилище")
    users_data_storage.add_or_update(telegram_id=user_telegram_id, data=new_store)
    print("Отправляю запрос к АПИ")
    answer = MessageReceiver.get_message(new_store)
    if answer.get("message", "no messages") == "no messages":
        await message.answer("Нет новых сообщений", reply_markup=user_menu_keyboard())
        await state.finish()
        return
    text = answer.get("message", "ERROR")
    token_work = answer.get("work", False)
    if token_work:
        print("Получаю ответ", text)
        await message.answer(f"Данные получены:"
                             f"\nСообщение: {text}")
        await UserState.user_wait_message.set()
    else:
        await message.answer(text, reply_markup=user_menu_keyboard())
        await state.finish()


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
    if result == "Message sent":
        await message.answer(f"Результат отправки: {result}", reply_markup=ReplyKeyboardRemove())
        await message.answer("Ожидаю новых сообщений", reply_markup=cancel_keyboard())
        await UserState.user_start_game.set()
        await start_command_handler(message=message, state=state)
        return
    else:
        await message.answer(f'При отправке сообщения произошла ошибка: {result}. Обратитесь к администратору.')
    await state.finish()


@logger.catch
async def default_message(message: Message) -> None:
    """Ответ на любое необработанное действие активного пользователя."""

    if User.is_active(message.from_user.id):
        await message.answer(
            'Доступные команды\n'
            '/start_parsing - Активирует бота.',
            reply_markup=user_menu_keyboard()
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
    dp.register_message_handler(start_command_handler, commands=["start_parsing", "старт"])
    dp.register_message_handler(info_tokens_handler, commands=["info"])
    dp.register_message_handler(start_command_handler, state=UserState.user_start_game)
    dp.register_message_handler(invitation_add_discord_token_handler, commands=["at", "addtoken", "add_token"])
    # dp.register_message_handler(set_self_token_cooldown_handler, commands=["set_cooldown"])
    dp.register_message_handler(add_discord_token_handler, state=UserState.user_add_token)
    dp.register_message_handler(send_to_discord, state=UserState.user_wait_message)
    dp.register_message_handler(add_discord_token_handler, state=UserState.user_add_token)
    dp.register_message_handler(add_channel_handler, state=UserState.user_add_channel)
    dp.register_message_handler(add_discord_id_handler, state=UserState.user_add_discord_id)
    dp.register_message_handler(add_language_handler, state=UserState.user_add_language)
    dp.register_message_handler(default_message)
