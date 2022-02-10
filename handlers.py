"""Модуль с основными обработчиками команд, сообщений и коллбэков"""
import asyncio
import datetime
import random
from typing import List, Set, Tuple

from aiogram.dispatcher.filters import Text
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher import FSMContext

from config import logger, Dispatcher
from models import User, UserTokenDiscord
from keyboards import cancel_keyboard, user_menu_keyboard, all_tokens_keyboard
from discord_handler import MessageReceiver, DataStore, users_data_storage, MessageSender
from states import UserState
from utils import check_is_int, save_data_to_json, send_report_to_admins, load_from_redis


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
        "Введите токен"
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
    # first_token = data.get('first_token')
    proxy: str = User.get_proxy(telegram_id=message.from_user.id)
    result = await DataStore.check_user_data(token=token, proxy=proxy, channel=channel)

    if result.get('token') == 'bad token':
        await message.answer(
            "Ваш токен не прошел проверку в данном канале. "
            "\nЛибо канал не существует либо токен отсутствует данном канале, "
            "\nЛибо токен не рабочий."
            "\nВведите ссылку на канал заново:",

            reply_markup=cancel_keyboard()
        )
        await UserState.user_add_channel.set()
        return

    await state.update_data(token=token)
    await state.update_data(proxb=proxy)

    await UserState.user_add_discord_id.set()
    link = "https://ibb.co/WHKKytW"
    await message.answer(
        f"Введите discord_id."
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

    if UserTokenDiscord.check_token_by_discord_id(discord_id=discord_id):
        await message.answer(
            "Такой discord_id уже был введен повторите ввод discord_id.",
            reply_markup=cancel_keyboard()
        )
        return

    data = await state.get_data()

    guild = data.get('guild')
    channel = data.get('channel')
    token = data.get('token')
    proxy = data.get('proxy')
    cooldown = data.get('cooldown')
    user = message.from_user.id

    token_result_complete: bool = UserTokenDiscord.add_token_by_telegram_id(
        telegram_id=user, token=token, discord_id=discord_id,
        proxy=proxy, guild=guild, channel=channel, cooldown=cooldown)

    if token_result_complete:
        await message.answer(
            "Токен удачно добавлен.",
            reply_markup=user_menu_keyboard())
        data = {
            user: data
        }
        save_data_to_json(data=data, file_name="user_data.json", key='a')
    else:
        UserTokenDiscord.delete_token(token)
        text = "ERROR: add_discord_id_handler: Не смог добавить токен, нужно вводить данные заново."
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
                f'Подписка истекает  {date_expiration}'
                'Данных о токенах нет.', reply_markup=user_menu_keyboard())


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
    work_hour: int = datetime.datetime.now().hour
    user_telegram_id: str = message.from_user.id

    while User.get_is_work(telegram_id=user_telegram_id):
        if (not User.check_expiration_date(telegram_id=user_telegram_id)
                and not User.is_admin(telegram_id=user_telegram_id)):
            await message.answer("Время подписки истекло.", reply_markup=cancel_keyboard())
            User.delete_user_by_telegram_id(telegram_id=user_telegram_id)
            logger.info(f"Время подписки {user_telegram_id} истекло, пользователь удален.")
            return
        answer: dict = await MessageReceiver.get_message(datastore=datastore)
        text: str = await api_errors_handler(telegram_id=user_telegram_id, answer=answer)
        if text == 'stop':
            return

        replies: list = answer.get("replies", [{}])
        if replies:
            await send_replies(message=message, replies=replies)

        token_work: bool = answer.get("work")
        if not token_work:
            if text != 'ok':
                await message.answer(text, reply_markup=cancel_keyboard())
            logger.info(f"PAUSE: {datastore.delay + 1}")
            current_hour: int = datetime.datetime.now().hour
            if current_hour > work_hour:
                work_hour: int = current_hour
                print("Время распределять токены!")
                await form_token_pairs(telegram_id=user_telegram_id, unpair=True)

            await asyncio.sleep(datastore.delay + 1)
            datastore.delay = 0
            await message.answer("Начинаю работу.", reply_markup=cancel_keyboard())


@logger.catch
async def send_replies(message: Message, replies: list):
    keyboard = InlineKeyboardMarkup(row_width=1)
    for reply in replies:
        author = reply.get("author")
        reply_id = reply.get("id")
        reply_text = reply.get("text")
        keyboard.add(InlineKeyboardButton(text=f'От: {author}\nText: {reply_text}', callback_data=f'reply_{reply_id}'))
    await message.answer(f"Вам пришли реплаи:", reply_markup=keyboard)


@logger.catch
async def answer_to_reply_handler(callback: CallbackQuery, state: FSMContext):
    message_id = callback.data.rsplit("_", maxsplit=1)[-1]
    await callback.message.answer('Что ответить?', reply_markup=cancel_keyboard())
    await UserState.answer_to_reply.set()
    await state.update_data(message_id=message_id)
    await callback.answer()


@logger.catch
async def send_message_to_reply_handler(message: Message, state: FSMContext):
    """Отправляет сообщение в дискорд реплаем на реплай"""

    state_data = await state.get_data()
    message_id = state_data.get("message_id")
    user_telegram_id = message.from_user.id
    token_data: List[dict] = await load_from_redis(telegram_id=user_telegram_id)
    token = ''
    for elem in token_data:
        if elem.get("message_id") == message_id:
            token = elem.get('token')
            break
    if not token:
        await send_report_to_admins(
            text="Func: send_message_to_reply_handler: "
            "Произошла ошибка получения токена из Redis"
        )
        return
    reply_store = DataStore(telegram_id=user_telegram_id)
    reply_store.save_token_data(token=token)
    reply_store.current_message_id = message_id
    answer = MessageSender(datastore=reply_store).send_message(text=message.text)
    if answer != "Message sent":
        await message.answer('Сообщение отправлено.', reply_markup=cancel_keyboard())
    else:
        await send_report_to_admins(
            text="Func: send_message_to_reply_handler: "
            "Произошла ошибка отправки реплая сообщения в функции "
        )
        return
    await state.finish()


@logger.catch
async def api_errors_handler(message: Message, answer: dict, datastore: 'DataStore') -> str:
    """Обработка ошибок от сервера"""

    user_telegram_id = message.from_user.id
    text = answer.get("message", "ERROR")

    if text == "API request error: 400":
        await send_report_to_admins(text)
        text = "stop"
    elif text == "API request error: 401":
        await message.answer(
            "Произошла ошибка данных. Убедитесь, что вы ввели верные данные. Код ошибки - 401.",
            reply_markup=user_menu_keyboard()
        )
        text = "stop"
    elif text == "API request error: 500":
        await send_report_to_admins("Внутренняя ошибка сервера Дискорда. Пауза 10 секунд. Код ошибки - 500.")
        datastore.delay = 10
        text = "ok"
    elif text == "API request error: 403":
        token = answer.get("token")
        UserTokenDiscord.delete_token(token=token)
        await message.answer(
            "У Вас нет прав отправлять сообщения в данный канал. (Ошибка 403). "
            "Похоже данный токен забанили/заглушили/токен сменился."
            f"\nТокен: {token} удален.",
            reply_markup=user_menu_keyboard()
        )
        await form_token_pairs(telegram_id=user_telegram_id, unpair=False)
        text = "ok"
    elif text == "Vocabulary error":
        await message.answer("Ошибка словаря.", reply_markup=user_menu_keyboard())
        await send_report_to_admins("Ошибка словаря.")
        text = "stop"
    elif text == "API request error: 429":
        await send_report_to_admins(
            "Слишком много запросов к АПИ. API request error: 429."
            "Может еще проксей добавим?"
        )
        datastore.delay = 10
        text = "ok"

    return text


@logger.catch
async def form_token_pairs(telegram_id: str, unpair: bool = False) -> None:
    """Формирует пары из свободных токенов если они в одном канале"""

    if unpair:
        User.delete_all_pairs(telegram_id=telegram_id)
    free_tokens: Tuple[tuple] = UserTokenDiscord.get_all_free_tokens(telegram_id=telegram_id)
    for channel, tokens in free_tokens:
        while len(tokens) > 1:
            random.shuffle(tokens)
            UserTokenDiscord.make_token_pair(tokens.pop(), tokens.pop())


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
    dp.register_callback_query_handler(answer_to_reply_handler, Text(startswith=["reply_"]))
    dp.register_message_handler(send_message_to_reply_handler, state=UserState.answer_to_reply)
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
