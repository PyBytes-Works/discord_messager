"""Модуль с основными обработчиками команд, сообщений и коллбэков"""

from typing import List
from collections import namedtuple

from aiogram.dispatcher.filters import Text
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
)
from aiogram.dispatcher import FSMContext

from classes.request_sender import RequestSender
from config import logger, Dispatcher, admins_list
from keyboards import cancel_keyboard, user_menu_keyboard, all_tokens_keyboard
from classes.discord_manager import DiscordTokenManager
from states import UserState
from utils import check_is_int, save_data_to_json, send_report_to_admins
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
async def get_all_tokens_handler(message: Message) -> None:
    """Обработчик команды "Установить кулдаун"""""

    if await DBI.is_expired_user_deactivated(message):
        return
    user_telegram_id: str = str(message.from_user.id)

    if await DBI.user_is_active(telegram_id=user_telegram_id):
        keyboard: 'InlineKeyboardMarkup' = await all_tokens_keyboard(user_telegram_id)
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
    await state.finish()
    await callback.answer()


@logger.catch
async def invitation_add_discord_token_handler(message: Message) -> None:
    """Обработчик команды /add_token"""

    if await DBI.is_expired_user_deactivated(message):
        return
    user_telegram_id: str = str(message.from_user.id)
    if await DBI.user_is_active(telegram_id=user_telegram_id):
        is_superadmin: bool = user_telegram_id in admins_list
        is_free_slots: bool = await DBI.get_number_of_free_slots_for_tokens(user_telegram_id) > 0
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
    link: str = "https://teletype.in/@ted_crypto/Txzfz8Vuwd2"
    await message.answer(
        "\nЧтобы узнать свой токен - перейдите по ссылке: "
        f"\n{link}"
    )
    await message.answer("Введите токен:", reply_markup=cancel_keyboard())
    await UserState.user_add_token.set()


@logger.catch
async def add_discord_token_handler(message: Message, state: FSMContext) -> None:
    """ Получение токена запрос discord_id """

    await message.answer("Проверяю данные.")
    token: str = message.text.strip()
    if await DBI.is_token_exists(token):
        await message.answer(
            "Такой токен токен уже есть в база данных."
            "\n Повторите ввод токена.",
            reply_markup=cancel_keyboard()
        )
        await UserState.user_add_token.set()
        return

    data: dict = await state.get_data()
    channel: int = data.get('channel')

    proxy: str = await RequestSender().get_checked_proxy(telegram_id=message.from_user.id)
    if proxy == 'no proxies':
        text: str = "Ошибка прокси. Нет доступных прокси."
        await message.answer(text, reply_markup=ReplyKeyboardRemove())
        await send_report_to_admins(text)
        await state.finish()
        return

    result: dict = await RequestSender().check_token(token=token, proxy=proxy, channel=channel)
    if not result.get("success"):
        error_message: str = result.get("message")
        if error_message == 'bad proxy':
            await message.answer(error_message, reply_markup=user_menu_keyboard())
            await state.finish()
            return
        elif error_message == 'bad token':
            await message.answer(
                f"Ваш токен {token} не прошел проверку в канале {channel}. "
                "\nЛибо канал не существует либо токен отсутствует данном канале, "
                "\nЛибо токен не рабочий."
                "\nВведите ссылку на канал заново:",

                reply_markup=cancel_keyboard()
            )
            await UserState.user_add_channel.set()
            return
        else:
            logger.error("f: add_discord_token_handler: error: Don`t know why")
            await state.finish()
            return

    # TODO get discord_id from get_me func

    token: str = result.get('token')
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

    if await DBI.check_token_by_discord_id(discord_id=discord_id):
        await message.answer(
            "Такой discord_id уже был введен повторите ввод discord_id.",
            reply_markup=cancel_keyboard()
        )
        return

    data: dict = await state.get_data()

    guild: int = data.get('guild')
    channel_id: int = data.get('channel')
    token: str = data.get('token')
    cooldown: int = data.get('cooldown')
    telegram_id: str = str(message.from_user.id)

    user_channel_pk: int = await DBI.add_user_channel(
        telegram_id=telegram_id, channel_id=channel_id, guild_id=guild, cooldown=cooldown)

    token_data: dict = {
        "telegram_id": telegram_id,
        "token": token,
        "discord_id": discord_id,
        "user_channel_pk": user_channel_pk,
    }

    token_result_complete: bool = await DBI.add_token_by_telegram_id(**token_data)
    if token_result_complete:
        await message.answer(
            "Токен удачно добавлен.",
            reply_markup=user_menu_keyboard())
        data = {
            telegram_id: data
        }
        save_data_to_json(data=data, file_name="../user_data.json", key='a')
        await DiscordTokenManager(message=message).form_token_pairs(unpair=False)
    else:
        await DBI.delete_token(token)
        text: str = "ERROR: add_discord_id_handler: Не смог добавить токен, нужно вводить данные заново."
        await message.answer(text, reply_markup=user_menu_keyboard())
        logger.error(text)
    await state.finish()


@logger.catch
async def info_tokens_handler(message: Message) -> None:
    """
    Выводит инфо о токенах. Обработчик кнопки "Информация"
    """

    if await DBI.is_expired_user_deactivated(message):
        return
    telegram_id: str = str(message.from_user.id)
    if await DBI.user_is_active(message.from_user.id):

        date_expiration: int = await DBI.get_expiration_date(telegram_id)
        all_tokens: List[namedtuple] = await DBI.get_all_tokens_info(telegram_id)
        count_tokens: int = len(all_tokens)
        free_slots: int = await DBI.get_number_of_free_slots_for_tokens(telegram_id)
        if not all_tokens:
            await message.answer(
                f'Подписка истекает  {date_expiration}'
                f'Данных о токенах нет.', reply_markup=user_menu_keyboard())
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
            mess: str = (
                f"Имя токена: {token_info.token_name}"
                f"Токен: {token_info.token}"
                f"\nКанал: {token_info.channel_id}"
                f"\nДискорд id: {token_info.token_discord_id}"
                f"\nДискорд id напарника: {token_info.mate_discord_id}"
                f"\nКуллдаун канала: {token_info.cooldown} сек."
            )
            keyboard: 'InlineKeyboardMarkup' = InlineKeyboardMarkup(row_width=1)
            keyboard.add(InlineKeyboardButton(
                text="Удалить токен.", callback_data=f"{token_info.token_pk}"))
            await message.answer(
                    mess,
                    reply_markup=keyboard
                )


@logger.catch
async def delete_token_handler(callback: CallbackQuery, state: FSMContext) -> None:
    """Хэндлер для нажатия на кнопку "Удалить токен" """

    telegram_id: str = str(callback.from_user.id)
    if await DBI.user_is_active(telegram_id):
        if await DBI.is_user_work(telegram_id=telegram_id):
            await callback.message.answer("Бот запущен, сначала остановите бота.", reply_markup=cancel_keyboard())
        else:
            await DBI.delete_token_by_pk(token_pk=int(callback.data))
            await callback.message.answer("Токен удален.", reply_markup=user_menu_keyboard())
            await callback.message.delete()
            await state.finish()
    await callback.answer()


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
    await UserState.in_work.set()
    await DiscordTokenManager(message=message, mute=mute).lets_play()
    # TODO добавить проверку - если все токены на КД - закончить работу
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
    dp.register_message_handler(info_tokens_handler, Text(equals=["Информация"]))
    dp.register_message_handler(get_all_tokens_handler, Text(equals=["Установить кулдаун"]))
    dp.register_callback_query_handler(request_self_token_cooldown_handler, state=UserState.select_token)
    dp.register_callback_query_handler(answer_to_reply_handler, Text(startswith=["reply_"]), state=UserState.in_work)
    dp.register_message_handler(send_message_to_reply_handler, state=UserState.in_work)
    dp.register_message_handler(invitation_add_discord_token_handler, Text(equals=["Добавить токен"]))
    dp.register_message_handler(add_cooldown_handler, state=UserState.user_add_cooldown)
    dp.register_message_handler(add_discord_token_handler, state=UserState.user_add_token)
    dp.register_message_handler(add_discord_token_handler, state=UserState.user_add_token)
    dp.register_message_handler(add_channel_handler, state=UserState.user_add_channel)
    dp.register_message_handler(add_discord_token_handler, state=UserState.user_add_token)
    dp.register_message_handler(add_discord_id_handler, state=UserState.user_add_discord_id)
    dp.register_callback_query_handler(delete_token_handler, state=UserState.user_delete_token)
    dp.register_message_handler(default_message)
