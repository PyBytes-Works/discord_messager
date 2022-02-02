"""Модуль с основными обработчиками команд, сообщений и коллбэков"""
import asyncio

from aiogram.dispatcher.filters import Text
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.dispatcher import FSMContext

from config import logger, Dispatcher
from models import User, UserTokenDiscord
from keyboards import cancel_keyboard, user_menu_keyboard, all_tokens_keyboard
from discord_handler import MessageReceiver, DataStore, MessageSender, users_data_storage
from states import UserState
from utils import check_is_int


@logger.catch
async def cancel_handler(message: Message, state: FSMContext) -> None:
    """
    Отменяет текущие запросы и сбрасывает состояние.
    Ставит пользователя в нерабочее состояние.
    Обработчик команды /cancel
    """

    user = message.from_user.id
    logger.info(f'CANCELED')
    await state.finish()
    await message.answer("Ввод отменен.", reply_markup=user_menu_keyboard())
    User.set_user_is_not_work(user)


@logger.catch
async def get_all_tokens_handler(message: Message) -> None:
    """Обработчик команды /set_cooldown"""

    user_telegram_id = message.from_user.id
    if User.is_active(telegram_id=user_telegram_id):
        await message.answer("Выберите токен: ", reply_markup=all_tokens_keyboard(user_telegram_id))

        await UserState.select_token.set()


@logger.catch
async def request_self_token_cooldown_handler(callback: CallbackQuery, state: FSMContext) -> None:
    """Обработчик нажатия на кнопку с токеном"""

    token = callback.data
    await state.update_data(token=token)
    await callback.message.answer("Введите время кулдауна в минутах", reply_markup=cancel_keyboard())
    await UserState.set_user_self_cooldown.set()

    await callback.answer()


@logger.catch
async def set_self_token_cooldown_handler(message: Message, state: FSMContext):
    """Получает время кулдауна в минутах, переводит в секунды, сохраняет новые данные для токена"""

    cooldown = check_is_int(message.text)
    if not cooldown:
        await message.answer(
            "Время должно быть целым, положительным числом. "
            "\nВведите время кулдауна в минутах.",
            reply_markup=cancel_keyboard()
        )
        return

    state_data = await state.get_data()
    token = state_data["token"]
    UserTokenDiscord.update_token_cooldown(token=token, cooldown=cooldown * 60)
    await message.answer(f"Кулдаун для токена [{token}] установлен: [{cooldown}] минут", reply_markup=cancel_keyboard())
    await state.finish()


@logger.catch
async def invitation_add_discord_token_handler(message: Message) -> None:
    """Обработчик команды /add_token"""

    # print(message.from_user.id)
    user = message.from_user.id
    if User.is_active(telegram_id=user):
        if UserTokenDiscord.get_number_of_free_slots_for_tokens(user):
            await message.answer(
                "Введите cooldown в минутах: ", reply_markup=cancel_keyboard())
            await UserState.user_add_cooldown.set()
            return
        await message.answer(
            "Максимальное количество discord-токенов уже добавлено", reply_markup=user_menu_keyboard())


@logger.catch
async def add_cooldown_handler(message: Message, state: FSMContext) -> None:
    """ Получение токена запрос ссылки на канал
    """

    cooldown = check_is_int(message.text)
    if not cooldown:
        await message.answer(
            "Попробуйте ещё раз cooldown должен быть целым положительным числом: ",
            reply_markup=cancel_keyboard())
        return

    await state.update_data(cooldown=cooldown * 60)
    await message.answer(
        "Введите ссылку на канал в виде: https://discord.com/channels/932034587264167975/932034858906401842",
        reply_markup=cancel_keyboard()
    )
    await UserState.user_add_channel.set()


@logger.catch
async def add_channel_handler(message: Message, state: FSMContext) -> None:
    """
        получения ссылки на канал, запрос token
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
    await UserState.user_add_token.set()
    await message.answer(
        "Введите первый токен", reply_markup=cancel_keyboard())


@logger.catch
async def add_discord_token_handler(message: Message, state: FSMContext) -> None:
    """ Получение токена запрос discord_id"""

    token = message.text
    token_info = UserTokenDiscord.get_info_by_token(token)
    if token_info:
        await message.answer(
            "Такой токен токен уже есть в база данных."
            "\n Повторите ввод токена.",
            reply_markup=cancel_keyboard()
        )
        await UserState.user_add_channel.set()
        return

    data = await state.get_data()
    channel = data.get('channel')
    first_token = data.get('first_token')
    proxy: str = User.get_proxy(telegram_id=message.from_user.id)
    result = await DataStore.check_user_data(token, proxy, channel)

    if result.get('token') == 'bad token':
        if not first_token:
            await message.answer(
                "Ваш токен не прошел проверку в данном канале. "
                "\nЛибо канал не существует либо токен отсутствует данном канале, "
                "\nЛибо токен не рабочий."
                "\n Повторите ввод токена.",

                reply_markup=cancel_keyboard()
            )
            await UserState.user_add_channel.set()
            return
        else:
            await message.answer(
                "Ваш токен не прошел проверку в данном канале. "
                "\nТокен отсутствует данном канале, либо токен не рабочий."
                "\n Повторите ввод токена.",
                reply_markup=cancel_keyboard()
            )
            return

    if first_token:
        await state.update_data(second_token=token)
        await state.update_data(second_proxy=proxy)
        mess_postfix = 'для второго токена'
    else:
        await state.update_data(first_token=token)
        await state.update_data(first_proxy=proxy)
        mess_postfix = 'для первого токена'

    await UserState.user_add_discord_id.set()
    await message.answer(
        f"введите discord_id {mess_postfix}", reply_markup=cancel_keyboard())


@logger.catch
async def add_discord_id_handler(message: Message, state: FSMContext) -> None:
    """
        добавить discord_id
    """

    discord_id = message.text
    # token = False  # TODO проверка используется ли дискорд id

    data = await state.get_data()
    first_discord_id = data.get('first_discord_id')

    if not first_discord_id:
        await state.update_data(first_discord_id=discord_id)
        await UserState.user_add_token.set()
        await message.answer(
            "Введите второй токен", reply_markup=cancel_keyboard())
        return

    guild = data.get('guild')
    channel = data.get('channel')
    second_discord_id = discord_id
    first_token = data.get('first_token')
    second_token = data.get('second_token')
    first_proxy = data.get('first_proxy')
    second_proxy = data.get('first_proxy')
    cooldown = data.get('cooldown')

    user = message.from_user.id
    token1 = UserTokenDiscord.add_token_by_telegram_id(
        telegram_id=user, token=first_token, discord_id=first_discord_id, mate_id=second_discord_id,
        proxy=first_proxy, guild=guild, channel=channel, cooldown=cooldown)
    token2 = UserTokenDiscord.add_token_by_telegram_id(
        telegram_id=user, token=second_token, discord_id=second_discord_id, mate_id=first_discord_id,
        proxy=second_proxy, guild=guild, channel=channel, cooldown=cooldown)
    if token1 and token2:
        await message.answer(
            "Токен добавлен",
            reply_markup=user_menu_keyboard())
    else:
        UserTokenDiscord.delete_token(first_token)
        UserTokenDiscord.delete_token(second_token)
        text = "ERROR: add_discord_id_handler: Не смог добавить токены, нужно вводить данные заново."
        await message.answer(text, reply_markup=user_menu_keyboard())
        logger.error(text)
    await state.finish()


@logger.catch
async def info_tokens_handler(message: Message, state: FSMContext) -> None:
    """выводит инфо о токенах. Обработчик кнопки /info
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
    Обработчик команды /start_parsing

    """
    user_telegram_id = message.from_user.id
    print(message.text)
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
    # result = await MessageReceiver.get_message(new_store)
    answer = await MessageReceiver.get_message(new_store)
    if answer.get("message", "no messages") == "no messages":
        await message.answer("Нет новых сообщений", reply_markup=user_menu_keyboard())
        await state.finish()
        return
    text = answer.get("message", "ERROR")
    token_work = answer.get("work", False)
    if not token_work:
        await message.answer(text, reply_markup=user_menu_keyboard())
        await state.finish()


#
# @logger.catch
# async def send_to_discord(message: Message, state: FSMContext) -> None:
#     """Отправляет полученное сообщение в дискорд"""
#
#     text = message.text
#     if len(text) > 50:
#         await message.answer(
#             "Сообщение не должно быть длиннее 50 символов. Попробуй еще раз.",
#             reply_markup=cancel_keyboard()
#         )
#         return
#     # await message.answer("Понял, принял, отправляю.", reply_markup=cancel_keyboard())
#
#     datastore = users_data_storage.get_instance(message.from_user.id)
#     result = MessageSender.send_message(text=message.text, datastore=datastore)
#     if result == "Message sent":
#         await message.answer(f"Результат отправки: {result}", reply_markup=ReplyKeyboardRemove())
#         # await message.answer("Ожидаю новых сообщений", reply_markup=cancel_keyboard())
#         await UserState.user_start_game.set()
#         await start_command_handler(message=message, state=state)
#         return
#     else:
#         await message.answer(f'При отправке сообщения произошла ошибка: {result}. Обратитесь к администратору.')
#     await state.finish()


@logger.catch
async def default_message(message: Message) -> None:
    """Ответ на любое необработанное действие активного пользователя."""

    if User.is_active(message.from_user.id):
        await message.answer(
            'Доступные команды: '
            '\n/start_parsing - Активирует бота.'
            '\n/add_token - Добавить токены.'
            '\n/set_cooldown - Назначить кулдаун для токена.'
            '\n/info - показать информацию по всем токенам пользователя.',
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
    dp.register_message_handler(start_command_handler, commands=["start_parsing"])
    dp.register_message_handler(info_tokens_handler, commands=["info"])
    dp.register_message_handler(start_command_handler, state=UserState.user_start_game)
    dp.register_message_handler(get_all_tokens_handler, commands=["set_cooldown"])
    dp.register_callback_query_handler(request_self_token_cooldown_handler, state=UserState.select_token)
    dp.register_message_handler(set_self_token_cooldown_handler, state=UserState.set_user_self_cooldown)
    dp.register_message_handler(invitation_add_discord_token_handler, commands=["at", "addtoken", "add_token"])
    dp.register_message_handler(add_cooldown_handler, state=UserState.user_add_cooldown)
    dp.register_message_handler(add_discord_token_handler, state=UserState.user_add_token)
    dp.register_message_handler(add_discord_token_handler, state=UserState.user_add_token)
    dp.register_message_handler(add_channel_handler, state=UserState.user_add_channel)
    dp.register_message_handler(add_discord_token_handler, state=UserState.user_add_token)
    dp.register_message_handler(add_discord_id_handler, state=UserState.user_add_discord_id)
    # dp.register_message_handler(send_to_discord, state=UserState.user_wait_message)
    dp.register_message_handler(default_message)
