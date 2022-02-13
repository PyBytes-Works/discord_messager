"""Модуль с основными обработчиками команд, сообщений и коллбэков"""

import asyncio
import datetime
import random
from typing import List, Tuple

from aiogram.dispatcher.filters import Text
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from aiogram.dispatcher import FSMContext

from config import logger, Dispatcher, admins_list
from models import User, Token
from keyboards import cancel_keyboard, user_menu_keyboard, all_tokens_keyboard
from discord_handler import MessageReceiver, DataStore, users_data_storage
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
    datastore: 'DataStore' = users_data_storage.get_instance(telegram_id=user_telegram_id)
    time_to_over: int = 0
    if datastore:
        time_to_over = datastore.delay
    logger.info(f'CANCELED')
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

    if await delete_user_if_expired(message=message):
        return
    user_telegram_id: str = str(message.from_user.id)

    if User.is_active(telegram_id=user_telegram_id):
        keyboard: 'InlineKeyboardMarkup' = all_tokens_keyboard(user_telegram_id)
        if not keyboard:
            await message.answer("Токенов нет. Нужно ввести хотя бы один.", reply_markup=user_menu_keyboard())
        else:
            await message.answer("Выберите токен: ", reply_markup=keyboard)
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

    if await delete_user_if_expired(message=message):
        return
    user: str = str(message.from_user.id)
    if User.is_active(telegram_id=user):
        is_superadmin: bool = user in admins_list
        if Token.get_number_of_free_slots_for_tokens(user) or is_superadmin:
            await message.answer(
                "Введите cooldown в минутах: ", reply_markup=cancel_keyboard())
            await UserState.user_add_cooldown.set()
            return
        await message.answer(
            "Максимальное количество discord-токенов уже добавлено", reply_markup=user_menu_keyboard())


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
        "Введите ссылку на канал в виде: https://discord.com/channels/932034587264167975/932034858906401842",
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
        logger.error(err)
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


@logger.catch
async def add_discord_token_handler(message: Message, state: FSMContext) -> None:
    """ Получение токена запрос discord_id """

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
    proxy: str = str(User.get_proxy(telegram_id=message.from_user.id))
    result: dict = await MessageReceiver.check_user_data(token=token, proxy=proxy, channel=channel)

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

    if await delete_user_if_expired(message=message):
        return
    user: str = str(message.from_user.id)
    if User.is_active(message.from_user.id):
        def get_mess(data: dict) -> str:
            if not data:
                return ''
            token: str = data.get('token')
            channel: int = data.get('channel')
            discord_id: int = data.get('discord_id')
            cooldown: int = data.get('cooldown')
            return (f"Токен: {token}"
                    f"\nКанал {channel}"
                    f"\nДискорд id {discord_id}"
                    f"\nКуллдаун {cooldown}")

        date_expiration = User.get_expiration_date(user)
        date_expiration = datetime.datetime.fromtimestamp(date_expiration)
        all_tokens: list = Token.get_all_info_tokens(user)
        if all_tokens:
            await UserState.user_delete_token_pair.set()
            await message.answer(
                f'Подписка истекает  {date_expiration}'
                f'\nТокены:',
                reply_markup=cancel_keyboard()
            )

            for token_info in all_tokens:
                token: str = token_info.get('token')
                mess: str = f'{get_mess(token_info)}'
                keyboard: 'InlineKeyboardMarkup' = InlineKeyboardMarkup(row_width=1)
                keyboard.add(InlineKeyboardButton(text="Удалить токен.", callback_data=f"{token}"))
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

    user: str = str(callback.from_user.id)
    if User.is_active(user):
        if User.get_is_work(telegram_id=user):
            await callback.message.answer("Бот запущен, сначала остановите бота.", reply_markup=cancel_keyboard())
        else:
            Token.delete_token(callback.data)
            await callback.message.delete()
            return

    await callback.answer()


@logger.catch
async def start_command_handler(message: Message, state: FSMContext) -> None:
    """Получает случайное сообщение из дискорда, ставит машину состояний в положение
    'жду ответа пользователя'
    Обработчик команды /start_parsing
    """

    user_telegram_id: str = str(message.from_user.id)
    if not User.is_active(telegram_id=user_telegram_id):
        return
    if await delete_user_if_expired(message=message):
        return
    if not Token.get_all_user_tokens(user_telegram_id):
        await message.answer("Сначала добавьте токен.", reply_markup=user_menu_keyboard())
        await state.finish()
        return

    User.set_user_is_work(telegram_id=user_telegram_id)
    await message.answer("Начинаю работу.", reply_markup=cancel_keyboard())
    await lets_play(message=message)
    await message.answer("Закончил работу.", reply_markup=user_menu_keyboard())

    await state.finish()


@logger.catch
async def lets_play(message: Message):
    """Show must go on
    Запускает рабочий цикл бота, проверяет ошибки."""

    work_hour: int = datetime.datetime.now().hour
    user_telegram_id: str = message.from_user.id

    while User.get_is_work(telegram_id=user_telegram_id):
        if await delete_user_if_expired(message=message):
            break
        datastore: 'DataStore' = DataStore(user_telegram_id)
        users_data_storage.add_or_update(telegram_id=user_telegram_id, data=datastore)
        message_manager: 'MessageReceiver' = MessageReceiver(datastore=datastore)
        answer: dict = await message_manager.get_message()
        text: str = await errors_handler(message=message, datastore=datastore, answer=answer)
        if text == 'stop':
            break

        replies: List[dict] = answer.get("replies", [])
        if replies:
            unanswered: list = await send_replies(message=message, replies=replies)
            # Остановит бота при реплаях. Можно удалить.
            # if unanswered:
            #     return
        token_work: bool = answer.get("work")
        if not token_work:
            if text != 'ok':
                await message.answer(text, reply_markup=cancel_keyboard())
            logger.info(f"PAUSE: {datastore.delay + 1}")
            current_hour: int = datetime.datetime.now().hour
            if current_hour > work_hour:
                work_hour: int = current_hour
                print("Время распределять токены!")
                form_token_pairs(telegram_id=user_telegram_id, unpair=True)

            await asyncio.sleep(datastore.delay + 1)
            datastore.delay = 0
            await message.answer("Начинаю работу.", reply_markup=cancel_keyboard())


@logger.catch
async def errors_handler(message: Message, answer: dict, datastore: 'DataStore') -> str:
    """Обработка ошибок от сервера"""

    user_telegram_id: str = str(message.from_user.id)
    text: str = answer.get("message", "ERROR")

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
        await send_report_to_admins(
            "Внутренняя ошибка сервера Дискорда. Пауза 10 секунд. Код ошибки - 500.")
        datastore.delay = 10
        text = "ok"
    elif text == "API request error: 403":
        token: str = answer.get("token")
        Token.delete_token(token=token)
        await message.answer(
            "У Вас нет прав отправлять сообщения в данный канал. (Ошибка 403). "
            "Похоже данный токен забанили/заглушили/токен сменился."
            f"\nТокен: {token} удален.",
            reply_markup=user_menu_keyboard()
        )
        form_token_pairs(telegram_id=user_telegram_id, unpair=False)
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
    elif text == "no pairs":
        pairs_formed: int = form_token_pairs(telegram_id=user_telegram_id, unpair=False)
        if not pairs_formed:
            text = "Не смог сформировать пары токенов."
            await message.answer(text)
            text = "stop"
        else:
            text = 'ok'

    return text


@logger.catch
async def send_replies(message: Message, replies: list):
    """Отправляет реплаи из дискорда в телеграм с кнопкой Ответить"""

    result = []
    answer_keyboard: 'InlineKeyboardMarkup' = InlineKeyboardMarkup(row_width=1)
    for reply in replies:
        answered: bool = reply.get("answered", False)
        if not answered:
            author: str = reply.get("author")
            reply_id: str = reply.get("message_id")
            reply_text: str = reply.get("text")
            answer_keyboard.add(InlineKeyboardButton(
                text="Ответить",
                callback_data=f'reply_{reply_id}'
            ))
            await message.answer(
                f"Вам пришло сообщение из ДИСКОРДА:"
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

    return formed_pairs


@logger.catch
async def default_message(message: Message) -> None:
    """Ответ на любое необработанное действие активного пользователя."""

    if User.is_active(message.from_user.id):
        if await delete_user_if_expired(message=message):
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
async def delete_user_if_expired(message: Message):
    """Удаляет пользователя с истекшим сроком действия."""

    user_telegram_id: str = str(message.from_user.id)
    user_active: bool = User.check_expiration_date(telegram_id=user_telegram_id)
    user_is_admin: bool = User.is_admin(telegram_id=user_telegram_id)
    if not user_active and not user_is_admin:
        await message.answer("Время подписки истекло. Ваш аккаунт удален.", reply_markup=ReplyKeyboardRemove())
        User.delete_user_by_telegram_id(telegram_id=user_telegram_id)
        logger.info(f"Время подписки {user_telegram_id} истекло, пользователь удален.")
        return True


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
