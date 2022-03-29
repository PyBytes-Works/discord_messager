"""Модуль с основными обработчиками команд, сообщений и коллбэков"""

import asyncio
import datetime
import random
from typing import List, Tuple

from aiogram.dispatcher.filters import Text
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from aiogram.dispatcher import FSMContext

from config import logger, Dispatcher, admins_list
from data_classes import users_data_storage
from models import User, Token
from keyboards import cancel_keyboard, user_menu_keyboard, all_tokens_keyboard
from discord_handler import MessageReceiver, TokenDataStore
from states import UserState
from utils import (
    check_is_int, save_data_to_json, send_report_to_admins, load_from_redis,
    save_to_redis
)


@logger.catch
async def cancel_handler(message: Message, state: FSMContext) -> None:
    """
    Отменяет текущие запросы и сбрасывает состояние.
    Ставит пользователя в нерабочее состояние.
    Обработчик команды /cancel
    """

    user_telegram_id: str = str(message.from_user.id)
    datastore: 'TokenDataStore' = users_data_storage.get_instance(telegram_id=user_telegram_id)
    time_to_over: int = 0
    if datastore:
        time_to_over = datastore.delay
    text: str = ''
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

    if await deactivate_user_if_expired(message=message):
        return
    user_telegram_id: str = str(message.from_user.id)

    if User.is_active(telegram_id=user_telegram_id):
        keyboard: 'InlineKeyboardMarkup' = all_tokens_keyboard(user_telegram_id)
        if not keyboard:
            await message.answer("Токенов нет. Нужно ввести хотя бы один.", reply_markup=cancel_keyboard())
        else:
            await message.answer("Выберите токен: ", reply_markup=keyboard)
            await message.answer("Или нажмите отмену.", reply_markup=cancel_keyboard())
            await UserState.select_token.set()


@logger.catch
async def request_self_token_cooldown_handler(callback: CallbackQuery, state: FSMContext) -> None:
    """Обработчик нажатия на кнопку с токеном"""

    token: str = callback.data
    await state.update_data(token=token)
    await callback.message.answer("Введите время кулдауна в минутах", reply_markup=cancel_keyboard())
    await UserState.set_user_self_cooldown.set()

    await callback.answer()


@logger.catch
async def set_self_token_cooldown_handler(message: Message, state: FSMContext):
    """Получает время кулдауна в минутах, переводит в секунды, сохраняет новые данные для токена"""

    cooldown: int = check_is_int(message.text)
    if not cooldown:
        await message.answer(
            "Время должно быть целым, положительным числом. "
            "\nВведите время кулдауна в минутах.",
            reply_markup=cancel_keyboard()
        )
        return

    state_data: dict = await state.get_data()
    token: str = state_data["token"]
    Token.update_token_cooldown(token=token, cooldown=cooldown * 60)
    await message.answer(f"Кулдаун для токена [{token}] установлен: [{cooldown}] минут", reply_markup=user_menu_keyboard())
    await state.finish()


@logger.catch
async def invitation_add_discord_token_handler(message: Message) -> None:
    """Обработчик команды /add_token"""

    if await deactivate_user_if_expired(message=message):
        return
    user: str = str(message.from_user.id)
    if User.is_active(telegram_id=user):
        is_superadmin: bool = user in admins_list
        is_free_slots: bool = Token.get_number_of_free_slots_for_tokens(user) > 0
        if is_free_slots or is_superadmin:
            await message.answer(
                "Введите cooldown в минутах: ", reply_markup=cancel_keyboard())
            await UserState.user_add_cooldown.set()
            return
        await message.answer(
            "Максимальное количество discord-токенов уже добавлено",
            reply_markup=user_menu_keyboard()
        )


@logger.catch
async def add_cooldown_handler(message: Message, state: FSMContext) -> None:
    """ Получение токена запрос ссылки на канал"""

    cooldown: int = check_is_int(message.text)
    if not cooldown:
        await message.answer(
            "Попробуйте ещё раз cooldown должен быть целым положительным числом: ",
            reply_markup=cancel_keyboard())
        return

    await state.update_data(cooldown=cooldown * 60)
    await message.answer(
        "Введите ссылку на канал в виде: "
        "https://discord.com/channels/932034587264167975/932034858906401842",
        reply_markup=cancel_keyboard()
    )
    await UserState.user_add_channel.set()


@logger.catch
async def add_channel_handler(message: Message, state: FSMContext) -> None:
    """
        Получения ссылки на канал, запрос токена
    """

    mess: str = message.text
    try:
        guild, channel = mess.rsplit('/', maxsplit=3)[-2:]
    except ValueError as err:
        logger.error("F: add_channel_handler error: err", err)
        guild: str = ''
        channel: str = ''
    guild: str = str(check_is_int(guild))
    channel: str = str(check_is_int(channel))
    if not guild or not channel:
        await message.answer(
            "Проверьте ссылку на канал и попробуйте ещё раз", reply_markup=cancel_keyboard())
        return

    await state.update_data(guild=guild, channel=channel)
    await UserState.user_add_token.set()
    link: str = "https://teletype.in/@ted_crypto/Txzfz8Vuwd2"
    await message.answer(
        "\nЧтобы узнать свой токен - перейдите по ссылке: "
        f"\n{link}"
    )
    await message.answer("Введите токен:", reply_markup=cancel_keyboard())


async def is_proxy_valid(message: Message, proxy: str) -> bool:
    if proxy != 'no proxies':
        return True
    text: str = "Ошибка прокси. Нет доступных прокси."
    await message.answer(text, reply_markup=ReplyKeyboardRemove())
    await send_report_to_admins(text)


@logger.catch
async def add_discord_token_handler(message: Message, state: FSMContext) -> None:
    """ Получение токена запрос discord_id """

    await message.answer("Проверяю данные.")
    token: str = message.text.strip()
    if Token.is_token_exists(token):
        await message.answer(
            "Такой токен токен уже есть в база данных."
            "\n Повторите ввод токена.",
            reply_markup=cancel_keyboard()
        )
        await UserState.user_add_token.set()
        return

    data: dict = await state.get_data()
    channel: int = data.get('channel')

    proxy: str = await MessageReceiver.get_proxy(telegram_id=message.from_user.id)
    if not await is_proxy_valid(message=message, proxy=proxy):
        await state.finish()
        return

    result: dict = await MessageReceiver.check_user_data(token=token, proxy=proxy, channel=channel)
    request_result: str = result.get('token')
    if not await is_proxy_valid(message=message, proxy=request_result):
        await state.finish()
        return

    if request_result == 'bad token':
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

    await UserState.user_add_discord_id.set()
    link: str = "https://ibb.co/WHKKytW"
    await message.answer(
        f"Введите discord_id."
        f"\nУзнать его можно перейдя по ссылке:"
        f"\n{link}",
        reply_markup=cancel_keyboard()
    )


@logger.catch
async def add_discord_id_handler(message: Message, state: FSMContext) -> None:
    """
        Проверяет данные токена и добавляет его в БД
    """

    discord_id: str = message.text.strip()

    if Token.check_token_by_discord_id(discord_id=discord_id):
        await message.answer(
            "Такой discord_id уже был введен повторите ввод discord_id.",
            reply_markup=cancel_keyboard()
        )
        return

    data: dict = await state.get_data()

    guild: int = data.get('guild')
    channel: int = data.get('channel')
    token: str = data.get('token')
    cooldown: int = data.get('cooldown')
    user: str = str(message.from_user.id)

    token_result_complete: bool = Token.add_token_by_telegram_id(
        telegram_id=user, token=token, discord_id=discord_id,
        guild=guild, channel=channel, cooldown=cooldown)
    if token_result_complete:
        await message.answer(
            "Токен удачно добавлен.",
            reply_markup=user_menu_keyboard())
        data = {
            user: data
        }
        save_data_to_json(data=data, file_name="user_data.json", key='a')
        form_token_pairs(telegram_id=user, unpair=False)
    else:
        Token.delete_token(token)
        text: str = "ERROR: add_discord_id_handler: Не смог добавить токен, нужно вводить данные заново."
        await message.answer(text, reply_markup=user_menu_keyboard())
        logger.error(text)
    await state.finish()


@logger.catch
async def info_tokens_handler(message: Message) -> None:
    """
    Выводит инфо о токенах. Обработчик кнопки /info
    """

    if await deactivate_user_if_expired(message=message):
        return
    user: str = str(message.from_user.id)
    if User.is_active(message.from_user.id):

        date_expiration = User.get_expiration_date(user)
        date_expiration = datetime.datetime.fromtimestamp(date_expiration)
        all_tokens: list = Token.get_all_info_tokens(user)
        count_tokens: int = len(all_tokens)
        free_slots: int = Token.get_number_of_free_slots_for_tokens(telegram_id=user)
        if not all_tokens:
            await message.answer(
                f'Подписка истекает  {date_expiration}'
                'Данных о токенах нет.', reply_markup=user_menu_keyboard())
            return

        await UserState.user_delete_token.set()
        await message.answer(
            f'Подписка истекает:  {date_expiration}'
            f'\nВсего токенов: {count_tokens}'
            f'\nСвободно слотов: {free_slots}'
            f'\nТокены:',
            reply_markup=cancel_keyboard()
        )

        for token_info in all_tokens:
            token_id: int = token_info.get('token_id')
            mess: str = (
                f"Токен: {token_info.get('token')}"
                f"\nКанал: {token_info.get('channel')}"
                f"\nДискорд id: {token_info.get('discord_id')}"
                f"\nДискорд id напарника: {token_info.get('mate_id', 'Напарника отсутствует.')}"
                f"\nКуллдаун: {token_info.get('cooldown')} сек."
            )
            keyboard: 'InlineKeyboardMarkup' = InlineKeyboardMarkup(row_width=1)
            keyboard.add(InlineKeyboardButton(text="Удалить токен.", callback_data=f"{token_id}"))
            await message.answer(
                    mess,
                    reply_markup=keyboard
                )


@logger.catch
async def delete_token_handler(callback: CallbackQuery, state: FSMContext) -> None:
    """Хэндлер для нажатия на кнопку "Удалить токен" """

    user: str = str(callback.from_user.id)
    if User.is_active(user):
        if User.get_is_work(telegram_id=user):
            await callback.message.answer("Бот запущен, сначала остановите бота.", reply_markup=cancel_keyboard())
        else:
            Token.delete_token_by_id(token_id=callback.data)
            await callback.message.answer("Токен удален.", reply_markup=user_menu_keyboard())
            await callback.message.delete()
            await state.finish()
    await callback.answer()


@logger.catch
async def start_parsing_command_handler(message: Message) -> None:
    """Получает случайное сообщение из дискорда, ставит машину состояний в положение
    'жду ответа пользователя'
    Обработчик команды /start_parsing
    """

    user_telegram_id: str = str(message.from_user.id)
    user_is_active: bool = User.is_active(telegram_id=user_telegram_id)
    if not user_is_active or await deactivate_user_if_expired(message=message):
        return
    if not Token.get_all_user_tokens(user_telegram_id):
        await message.answer("Сначала добавьте токен.", reply_markup=user_menu_keyboard())
        return
    if User.get_is_work(telegram_id=user_telegram_id):
        await message.answer("Бот уже запущен.")
        return
    User.set_user_is_work(telegram_id=user_telegram_id)
    await message.answer("Начинаю работу.", reply_markup=cancel_keyboard())
    await lets_play(message=message)
    await message.answer("Закончил работу.", reply_markup=user_menu_keyboard())


@logger.catch
async def lets_play(message: Message):
    """Show must go on
    Запускает рабочий цикл бота, проверяет ошибки."""

    user_telegram_id: str = str(message.from_user.id)
    while User.get_is_work(telegram_id=user_telegram_id):
        if await deactivate_user_if_expired(message=message):
            break
        datastore: 'TokenDataStore' = TokenDataStore(user_telegram_id)
        users_data_storage.add_or_update(telegram_id=user_telegram_id, data=datastore)
        message_manager: 'MessageReceiver' = MessageReceiver(datastore=datastore)

        discord_data: dict = await message_manager.get_message()
        if not discord_data:
            await send_report_to_admins("Произошла какая то чудовищная ошибка в функции lets_play.")
            break
        token_work: bool = discord_data.get("work")

        replies: List[dict] = discord_data.get("replies", [])
        if replies:
            await send_replies(message=message, replies=replies)
        if not token_work:
            text: str = await get_error_text(
                message=message, datastore=datastore, discord_data=discord_data
            )
            if text == 'stop':
                break
            elif text != 'ok':
                await message.answer(text, reply_markup=cancel_keyboard())
            logger.info(f"PAUSE: {datastore.delay + 1}")
            if not datetime.datetime.now().minute % 10:
                form_token_pairs(telegram_id=user_telegram_id, unpair=True)
                logger.info(f"Время распределять токены!")

            await asyncio.sleep(datastore.delay + 1)
            datastore.delay = 0
            await message.answer("Начинаю работу.", reply_markup=cancel_keyboard())
        await asyncio.sleep(1 / 1000)


@logger.catch
async def get_error_text(message: Message, discord_data: dict, datastore: 'TokenDataStore') -> str:
    """Обработка ошибок от сервера"""

    user_telegram_id: str = str(message.from_user.id)
    text: str = discord_data.get("message", "ERROR")
    token: str = discord_data.get("token")

    answer: dict = discord_data.get("answer", {})
    data: dict = answer.get("data", {})
    status_code: int = answer.get("status_code", 0)
    sender_text: str = answer.get("message", "SEND_ERROR")
    discord_code_error: int = answer.get("data", {}).get("code", 0)

    result: str = 'ok'

    if text == "no pairs":
        pairs_formed: int = form_token_pairs(telegram_id=user_telegram_id, unpair=False)
        if not pairs_formed:
            await message.answer("Не смог сформировать пары токенов.")
            result = 'stop'
    elif status_code == -1:
        error_text = sender_text
        await message.answer("Ошибка десериализации отправки ответа.")
        await send_report_to_admins(error_text)
        result = "stop"
    elif status_code == -2:
        await message.answer("Ошибка словаря.", reply_markup=user_menu_keyboard())
        await send_report_to_admins("Ошибка словаря.")
        result = "stop"
    elif status_code == 400:
        if discord_code_error == 50035:
            sender_text = 'Сообщение для ответа удалено из дискорд канала.'
        else:
            result = "stop"
        await send_report_to_admins(sender_text)
    elif status_code == 401:
        if discord_code_error == 0:
            await message.answer("Сменился токен."
                                 f"\nToken: {token}")
        else:
            await message.answer(
                "Произошла ошибка данных. Убедитесь, что вы ввели верные данные. Код ошибки - 401.",
                reply_markup=user_menu_keyboard()
            )
        result = "stop"
    elif status_code == 403:
        if discord_code_error == 50013:
            await message.answer(
                "Не могу отправить сообщение для токена. (Ошибка 403 - 50013)"
                "Токен в муте."
                f"\nToken: {token}"
                f"\nGuild: {datastore.guild}"
                f"\nChannel: {datastore.channel}"
            )
        elif discord_code_error == 50001:
            Token.delete_token(token=token)
            await message.answer(
                "Не могу отправить сообщение для токена. (Ошибка 403 - 50001)"
                "Токен забанили."
                f"\nТокен: {token} удален."
                f"\nФормирую новые пары.",
                reply_markup=user_menu_keyboard()
            )
            form_token_pairs(telegram_id=user_telegram_id, unpair=False)
        else:
            await message.answer(f"Ошибка {status_code}: {data}")
    elif status_code == 404:
        if discord_code_error == 10003:
            await message.answer(
                "Ошибка отправки сообщения. Неверный канал. (Ошибка 404 - 10003)"
                f"\nToken: {token}"
            )
        else:
            await message.answer(f"Ошибка {status_code}: {data}")
    elif status_code == 407:
        await message.answer("Ошибка прокси. Обратитесь к администратору. Код ошибки 407.", reply_markup=ReplyKeyboardRemove())
        await send_report_to_admins(f"Ошибка прокси. Время действия proxy истекло.")
        result = "stop"
    elif status_code == 429:
        if discord_code_error == 20016:
            cooldown: int = int(data.get("retry_after", None))
            if cooldown:
                cooldown += datastore.cooldown + 2
                Token.update_token_cooldown(token=token, cooldown=cooldown)
                Token.update_mate_cooldown(token=token, cooldown=cooldown)
                datastore.delay = cooldown
            await message.answer(
                "Для данного токена сообщения отправляются чаще, чем разрешено в канале."
                f"\nToken: {token}"
                f"\nВремя скорректировано. Кулдаун установлен: {cooldown} секунд"
            )
        else:
            await message.answer(f"Ошибка: {status_code}:{discord_code_error}:{sender_text}")
    elif status_code == 500:
        error_text = (
            f"Внутренняя ошибка сервера Дискорда. "
            f"\nГильдия:Канал: {datastore.guild}:{datastore.channel} "
            f"\nПауза 10 секунд. Код ошибки - 500."
        )
        await message.answer(error_text)
        await send_report_to_admins(error_text)
        datastore.delay = 10
    else:
        result = text

    return result


@logger.catch
async def send_replies(message: Message, replies: list):
    """Отправляет реплаи из дискорда в телеграм с кнопкой Ответить"""

    result = []
    for reply in replies:
        answered: bool = reply.get("answered", False)
        if not answered:
            answer_keyboard: 'InlineKeyboardMarkup' = InlineKeyboardMarkup(row_width=1)
            author: str = reply.get("author")
            reply_id: str = reply.get("message_id")
            reply_text: str = reply.get("text")
            reply_to_author: str = reply.get("to_user")
            reply_to_message: str = reply.get("to_message")
            answer_keyboard.add(InlineKeyboardButton(
                text="Ответить",
                callback_data=f'reply_{reply_id}'
            ))
            await message.answer(
                f"Вам пришло сообщение из ДИСКОРДА:"
                f"\nКому: {reply_to_author}"
                f"\nНа сообщение: {reply_to_message}"
                f"\nОт: {author}"
                f"\nText: {reply_text}",
                reply_markup=answer_keyboard
            )
            result.append(reply)

    return result


@logger.catch
async def answer_to_reply_handler(callback: CallbackQuery, state: FSMContext):
    """Запрашивает текст ответа на реплай для отправки в дискорд"""

    message_id: str = callback.data.rsplit("_", maxsplit=1)[-1]
    await callback.message.answer('Введите текст ответа:', reply_markup=cancel_keyboard())
    await UserState.answer_to_reply.set()
    await state.update_data(message_id=message_id)
    await callback.answer()


@logger.catch
async def send_message_to_reply_handler(message: Message, state: FSMContext):
    """Отправляет сообщение в дискорд реплаем на реплай"""

    state_data: dict = await state.get_data()
    message_id: str = state_data.get("message_id")
    user_telegram_id: str = str(message.from_user.id)
    redis_data: List[dict] = await load_from_redis(telegram_id=user_telegram_id)
    for elem in redis_data:
        if str(elem.get("message_id")) == str(message_id):
            elem.update({"answer_text": message.text})
            break
    else:
        logger.warning("f: send_message_to_reply_handler: elem in Redis data not found.")
        await message.answer('Время хранения данных истекло.', reply_markup=cancel_keyboard())
        await state.finish()
        return
    await message.answer('Добавляю сообщение в очередь. Это займет несколько секунд.', reply_markup=ReplyKeyboardRemove())
    await save_to_redis(telegram_id=user_telegram_id, data=redis_data)
    await message.answer('Сообщение добавлено в очередь сообщений.', reply_markup=cancel_keyboard())
    await state.finish()


@logger.catch
def form_token_pairs(telegram_id: str, unpair: bool = False) -> int:
    """Формирует пары из свободных токенов если они в одном канале"""

    if unpair:
        User.delete_all_pairs(telegram_id=telegram_id)
    free_tokens: Tuple[Tuple[str, list]] = Token.get_all_free_tokens(telegram_id=telegram_id)
    formed_pairs: int = 0
    for channel, tokens in free_tokens:
        while len(tokens) > 1:
            random.shuffle(tokens)
            formed_pairs += Token.make_tokens_pair(tokens.pop(), tokens.pop())
    logger.info(f"Pairs formed: {formed_pairs}")

    return formed_pairs


@logger.catch
async def default_message(message: Message) -> None:
    """Ответ на любое необработанное действие активного пользователя."""

    if User.is_active(message.from_user.id):
        if await deactivate_user_if_expired(message=message):
            return
        await message.answer(
            'Доступные команды: '
            '\n/start_parsing - Активирует бота.'
            '\n/add_token - Добавить токены.'
            '\n/set_cooldown - Назначить кулдаун для токена.'
            '\n/info - показать информацию по всем токенам пользователя.',
            reply_markup=user_menu_keyboard()
        )


@logger.catch
async def deactivate_user_if_expired(message: Message) -> bool:
    """Удаляет пользователя с истекшим сроком действия.
    Возвращает True если деактивирован."""

    user_telegram_id: str = str(message.from_user.id)
    user_not_expired: bool = User.check_expiration_date(telegram_id=user_telegram_id)
    user_is_admin: bool = User.is_admin(telegram_id=user_telegram_id)
    if not user_not_expired and not user_is_admin:
        await message.answer(
            "Время подписки истекло. Ваш аккаунт деактивирован, токены удалены.",
            reply_markup=ReplyKeyboardRemove()
        )
        User.delete_all_tokens(telegram_id=user_telegram_id)
        User.deactivate_user(telegram_id=user_telegram_id)
        text = (
            f"Время подписки {user_telegram_id} истекло, "
            f"пользователь декативирован, его токены удалены"
        )
        logger.info(text)
        await send_report_to_admins(text)
        return True

    return False


@logger.catch
async def start_command_handler(message: Message):
    """Активирует пользователя если он валидный"""

    user_telegram_id: str = str(message.from_user.id)
    user_not_expired: bool = User.check_expiration_date(telegram_id=user_telegram_id)
    user_activated: bool = User.is_active(telegram_id=user_telegram_id)
    if user_not_expired and not user_activated:
        User.activate_user(telegram_id=user_telegram_id)
        await message.answer("Аккаунт активирован.")


@logger.catch
def register_handlers(dp: Dispatcher) -> None:
    """
    Регистратор для функций данного модуля
    """

    dp.register_message_handler(
        cancel_handler, commands=['отмена', 'cancel'], state="*")
    dp.register_message_handler(
        cancel_handler, Text(startswith=["отмена", "cancel"], ignore_case=True), state="*")
    dp.register_callback_query_handler(
        cancel_handler, Text(startswith=["отмена", "cancel"], ignore_case=True), state="*")
    dp.register_message_handler(start_parsing_command_handler, commands=["start_parsing"])
    dp.register_message_handler(start_command_handler, commands=["start"])
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
    dp.register_callback_query_handler(delete_token_handler, state=UserState.user_delete_token)
    dp.register_message_handler(default_message)
