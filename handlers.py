"""Модуль с основными обработчиками команд, сообщений и коллбэков"""
import asyncio
import datetime

from aiogram.dispatcher.filters import Text
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher import FSMContext

from config import logger, Dispatcher
from models import User, UserTokenDiscord
from keyboards import cancel_keyboard, user_menu_keyboard, all_tokens_keyboard
from discord_handler import MessageReceiver, DataStore, users_data_storage
from states import UserState
from utils import check_is_int, save_data_to_json


@logger.catch
async def cancel_handler(message: Message, state: FSMContext) -> None:
    """
    Отменяет текущие запросы и сбрасывает состояние.
    Ставит пользователя в нерабочее состояние.
    Обработчик команды /cancel
    """

    user_telegram_id = message.from_user.id
    datastore = users_data_storage.get_instance(telegram_id=user_telegram_id)
    time_to_over = 0
    if datastore:
        time_to_over = datastore.delay
    logger.info(f'CANCELED')
    text = ''
    if User.get_is_work(telegram_id=user_telegram_id):
        text = ("\nДождитесь завершения работы бота..."
                f"\nОсталось: {time_to_over} секунд")
    await message.answer(
        "Вы отменили текущую команду." + text,
        reply_markup=user_menu_keyboard()
    )
    User.set_user_is_not_work(telegram_id=user_telegram_id)
    await state.finish()


@logger.catch
async def get_all_tokens_handler(message: Message) -> None:
    """Обработчик команды /set_cooldown"""

    user_telegram_id = message.from_user.id

    if User.is_active(telegram_id=user_telegram_id):
        keyboard = all_tokens_keyboard(user_telegram_id)
        if not keyboard:
            await message.answer("Токенов нет. Нужно ввести хотя бы два.", reply_markup=user_menu_keyboard())
        else:
            await message.answer("Выберите токен: ", reply_markup=keyboard)
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
    await message.answer(f"Кулдаун для токена [{token}] установлен: [{cooldown}] минут", reply_markup=user_menu_keyboard())
    await state.finish()


@logger.catch
async def invitation_add_discord_token_handler(message: Message) -> None:
    """Обработчик команды /add_token"""

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
    """ Получение токена запрос ссылки на канал"""

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
        Получения ссылки на канал, запрос tokenа
    """

    mess = message.text
    try:
        guild, channel = mess.rsplit('/', maxsplit=3)[-2:]
    except ValueError as err:
        logger.error(err)
        guild = channel = 0
    guild = check_is_int(guild)
    channel = check_is_int(channel)
    if not guild or not channel:
        await message.answer(
            "Проверьте ссылку на канал и попробуйте ещё раз", reply_markup=cancel_keyboard())
        return

    await state.update_data(guild=guild, channel=channel)
    await UserState.user_add_token.set()
    link = "https://teletype.in/@ted_crypto/Txzfz8Vuwd2"
    await message.answer(
        "Введите первый токен"
        "\nЧтобы узнать свой токен - перейдите по ссылке: "
        f"\n{link}",
        reply_markup=cancel_keyboard()
    )


@logger.catch
async def add_discord_token_handler(message: Message, state: FSMContext) -> None:
    """ Получение токена запрос discord_id"""

    token = message.text.strip()
    token_info = UserTokenDiscord.get_info_by_token(token)
    if token_info:
        await message.answer(
            "Такой токен токен уже есть в база данных."
            "\n Повторите ввод токена.",
            reply_markup=cancel_keyboard()
        )
        await UserState.user_add_token.set()
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
                "\nВведите ссылку на канал заново:",

                reply_markup=cancel_keyboard()
            )
            await UserState.user_add_channel.set()
            return
        else:
            await message.answer(
                "Ваш токен не прошел проверку в данном канале. "
                "\nТокен отсутствует данном канале, либо токен не рабочий."
                "\nПовторите ввод токена.",
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
    link = "https://ibb.co/WHKKytW"
    await message.answer(
        f"Введите discord_id {mess_postfix}"
        f"\nУзнать его можно перейдя по ссылке:"
        f"\n{link}",
        reply_markup=cancel_keyboard()
    )


@logger.catch
async def add_discord_id_handler(message: Message, state: FSMContext) -> None:
    """
        Проверяет оба токена и добавляет их в БД
    """

    discord_id = message.text.strip()

    data = await state.get_data()
    first_discord_id = data.get('first_discord_id')
    check_discord_id = UserTokenDiscord.check_token_by_discord_id(discord_id=discord_id)

    if check_discord_id or discord_id == first_discord_id:
        await message.answer(
            "Такой discord_id уже был введен повторите ввод discord_id.",
            reply_markup=cancel_keyboard()
        )
        return

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
    data.update({
        "second_discord_id": discord_id,
    })
    if token1 and token2:
        await message.answer(
            "Токены удачно добавлены.",
            reply_markup=user_menu_keyboard())
        data = {
            user: data
        }
        save_data_to_json(data=data, file_name="user_data.json", key='a')
    else:
        UserTokenDiscord.delete_token(first_token)
        UserTokenDiscord.delete_token(second_token)
        text = "ERROR: add_discord_id_handler: Не смог добавить токены, нужно вводить данные заново."
        await message.answer(text, reply_markup=user_menu_keyboard())
        logger.error(text)
    await state.finish()


@logger.catch
async def info_tokens_handler(message: Message) -> None:
    """
    Выводит инфо о токенах. Обработчик кнопки /info
    """

    user = message.from_user.id
    if User.is_active(message.from_user.id):
        def get_mess(data: dict) -> str:
            if not data:
                return ''
            token = data.get('token')
            channel = data.get('channel')
            discord_id = data.get('discord_id')
            mate_id = data.get('mate_id')
            cooldown = data.get('cooldown')
            return (f"Токен: {token}"
                    f"\nКанал {channel}"
                    f"\nДискорд id {discord_id}"
                    f"\nID пары  {mate_id}"
                    f"\nКуллдаун {cooldown}")

        date_expiration = User.get_expiration_date(user)
        date_expiration = datetime.datetime.fromtimestamp(date_expiration)
        data = UserTokenDiscord.get_all_info_tokens(user)
        if data:
            await UserState.user_delete_token_pair.set()
            await message.answer(
                f'Подписка истекает  {date_expiration}'
                f'\nПары токенов:',
                reply_markup=cancel_keyboard()
            )

            for token_info in data:
                first_token = token_info[0].get('token')
                mess = f'1) {get_mess(token_info[0])} \n2) {get_mess(token_info[1])}'
                keyboard = InlineKeyboardMarkup(row_width=1)
                keyboard.add(InlineKeyboardButton(text="Удалить пару.", callback_data=f"{first_token}"))
                await message.answer(
                        mess,
                        reply_markup=keyboard
                    )
        else:
            await message.answer(
                "f'Подписка истекает  {date_expiration}"
                "'Данных о токенах нет.", reply_markup=user_menu_keyboard())


@logger.catch
async def delete_pair_handler(callback: CallbackQuery) -> None:
    """Хэндлер для нажатия на кнопку "Удалить токен" """

    user = callback.from_user.id
    if User.is_active(user):
        if User.get_is_work(telegram_id=user):
            await callback.message.answer("Бот запущен, сначала остановите бота.", reply_markup=cancel_keyboard())
        else:
            UserTokenDiscord.delete_token_pair(callback.data)
            await callback.message.delete()
            return

    await callback.answer()


@logger.catch
async def start_command_handler(message: Message, state: FSMContext) -> None:
    """Получает случайное сообщение из дискорда, ставит машину состояний в положение
    'жду ответа пользователя'
    Обработчик команды /start_parsing
    """

    user_telegram_id = message.from_user.id
    if not User.is_active(telegram_id=user_telegram_id):
        return
    if not UserTokenDiscord.get_all_user_tokens(user_telegram_id):
        await message.answer("Сначала добавьте токен.", reply_markup=user_menu_keyboard())
        await state.finish()
        return

    datastore = DataStore(user_telegram_id)
    users_data_storage.add_or_update(telegram_id=user_telegram_id, data=datastore)
    User.set_user_is_work(telegram_id=user_telegram_id)
    await message.answer("Начинаю работу.", reply_markup=cancel_keyboard())
    await lets_play(message=message, datastore=datastore)
    await state.finish()


@logger.catch
async def lets_play(message: Message, datastore: 'DataStore'):
    """Show must go on"""

    user_telegram_id = message.from_user.id
    while User.get_is_work(telegram_id=user_telegram_id):
        if (not User.check_expiration_date(telegram_id=user_telegram_id)
                and not User.is_admin(telegram_id=user_telegram_id)):
            await message.answer("Время подписки истекло.", reply_markup=cancel_keyboard())
            User.delete_user_by_telegram_id(telegram_id=user_telegram_id)
            logger.info(f"Время подписки {user_telegram_id} истекло, пользователь удален.")
            return
        answer = await MessageReceiver.get_message(datastore=datastore)
        text = answer.get("message", "ERROR")
        if text == "API request error: 400":
            await message.answer(text, reply_markup=user_menu_keyboard())
            return
        elif text == "API request error: 403":
            await message.answer(
                "У Вас нет прав отправлять сообщения в данный канал.",
                reply_markup=user_menu_keyboard()
            )
            return
        elif text == "Vocabulary error":
            await message.answer("Ошибка словаря.", reply_markup=user_menu_keyboard())
            return
        token_work = answer.get("work")
        if not token_work:
            await message.answer(text, reply_markup=cancel_keyboard())
            logger.info(f"PAUSE: {datastore.delay + 1}")
            await asyncio.sleep(datastore.delay + 1)
            datastore.delay = 0
            await message.answer("Начинаю работу.", reply_markup=cancel_keyboard())


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
    dp.register_callback_query_handler(delete_pair_handler, state=UserState.user_delete_token_pair)
    dp.register_message_handler(default_message)
