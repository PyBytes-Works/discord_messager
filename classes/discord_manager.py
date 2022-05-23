import random
from typing import List, Optional, Tuple
from collections import namedtuple

import asyncio

from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from classes.message_manager import MessageManager
from classes.message_sender import MessageSender
from classes.open_ai import OpenAI
from classes.replies import RepliesManager
from classes.token_datastorage import TokenData

from config import logger, SEMAPHORE
from classes.db_interface import DBI
from decorators.decorators import check_working, info_logger
from keyboards import user_menu_keyboard, in_work_keyboard
from utils import get_current_timestamp


class DiscordManager:
    """Bot work manager. Checking tokens data, getting and sending requests
    to discord.

    Methods:
        lets_play - start bot working

    Attributes:
        message: 'Message' - instance of aiogram Message class
        silence: bool - flag for silence mode
        is_working: bool - flag for check working mode
        auto_answer: bool - flag for OpenAI autoanswer to replies from discord
        reboot: bool - if True - dont start working than server will not rebooted yet
        delay: int - time for sleep after all tokens worked
        datastore: 'TokenData' - instance of TokenData class
    """

    def __init__(self, message: Message = None) -> None:
        self.message: 'Message' = message
        self._telegram_id: str = str(self.message.from_user.id) if message else ''
        self.datastore: Optional['TokenData'] = TokenData(self._telegram_id)
        self.semaphore = SEMAPHORE
        self.delay: int = 0
        self.is_working: bool = False
        self.auto_answer: bool = False
        self.reboot: bool = False
        self.silence: bool = False
        self._username: str = message.from_user.username if message else ''
        self.total_tokens_count: int = 0
        self.__workers: List['TokenData'] = []
        self.__all_user_tokens_discord_ids: List[str] = []
        self.__token_work_time: int = 10
        self.channels_list: List[List[namedtuple]] = []
        self.min_cooldown: int = 60

    @info_logger
    @logger.catch
    async def lets_play(self) -> None:
        """Show must go on
        Запускает рабочий цикл бота, проверяет ошибки."""

        # TODO сделать команду для отображения работающих в данный момент пользователей

        await self._get_all_discord_ids()

        while self.is_working:
            await self._lets_play()

    @logger.catch
    async def _lets_play(self) -> None:

        await self.__check_reboot()
        await self._check_user_active()
        await self._make_working_data()
        async with self.semaphore:
            await self._handling_received_messages()
            await self._send_replies()
            answer: dict = await self._sending_messages()
            await self._handling_errors(answer)
        await self._sleep()

    @logger.catch
    async def __check_reboot(self) -> None:
        """Проверяет флаг reboot и если он True - завершает работу бота"""

        # TODO сделать декоратор из reboot
        if self.reboot:
            await self.message.answer(
                "Ожидайте перезагрузки сервера.",
                reply_markup=user_menu_keyboard())
            self.is_working = False

    @logger.catch
    async def __get_full_info(self) -> str:
        return (
            f"\n\tUsername: {self._username}"
            f"\n\tProxy: {self.datastore.proxy}"
            f"\n\tUser telegram id: {self._telegram_id}"
            f"\n\tToken: {self.datastore.token}"
            f"\n\tChannel: {self.datastore.channel}"
            f"\n\tDiscord ID: {self.datastore.my_discord_id}"
            f"\n\tMate discord id: {self.datastore.mate_id}"
            f"\n\tSilence: {self.silence}"
            f"\n\tAutoanswer: {self.auto_answer}"
            f"\n\tWorkers: {len(self.__workers)}/{self.total_tokens_count}"
            f"\n\tDelay: {self.delay}"
            f"\n\tTokens cooldowns:\n\t\t"
        )

    @logger.catch
    async def _check_user_active(self):
        """Проверяет активный ли пользователь и не истекла ли у него подписка"""

        user_is_admin: bool = await DBI.is_admin(telegram_id=self._telegram_id)
        user_is_superadmin: bool = await DBI.is_superadmin(telegram_id=self._telegram_id)
        if user_is_admin or user_is_superadmin:
            return
        user_deactivated: bool = await DBI.is_expired_user_deactivated(self.message)
        user_is_work: bool = await DBI.is_user_work(telegram_id=self._telegram_id)
        if user_deactivated or not user_is_work:
            await self.message.answer(
                "Работа завершена - пользователь не работает или деактивирован")
            self.is_working = False

    @logger.catch
    async def _get_all_discord_ids(self):
        """Получает дискорд ИД всех токенов пользователя."""

        ids: List[str] = await DBI.get_all_discord_id(self._telegram_id)
        if ids and len(ids) > 1:
            self.__all_user_tokens_discord_ids = ids
            self.is_working = True
            return
        await self.message.answer("Недостаточно токенов.")

    @check_working
    @logger.catch
    async def _handling_received_messages(self) -> None:
        """Получает сообщения из чата и обрабатывает их"""

        if not all((self.datastore.token, self.datastore.channel)):
            logger.error(f"\nError: TG: {self.datastore.telegram_id}"
                         f"\nToken: {self.datastore.token}"
                         f"\nChannel: {self.datastore.channel}")
            return
        self.datastore.token_time_delta = (
                (self.total_tokens_count - len(self.__workers))
                * self.__token_work_time
        )
        logger.debug(f"{self.datastore.token_time_delta=}")
        await MessageManager(datastore=self.datastore).handling_messages()
        await self.__is_token_deleted()

    @logger.catch
    async def __is_token_deleted(self) -> bool:
        if self.datastore.need_to_delete:
            token = self.datastore.token
            if await DBI.delete_token(token=token):
                text: str = f"\nТокен удален:\n" + token
                logger.warning(text)
                await self.message.answer(text)
            await self._make_token_pairs()
            return True
        return False

    @check_working
    @logger.catch
    async def _sending_messages(self) -> dict:
        """Отправляет сообщение в дискорд"""

        if not all((self.datastore.token, self.datastore.channel)):
            logger.error(f"\nError: TG: {self.datastore.telegram_id}"
                         f"\nToken: {self.datastore.token}"
                         f"\nChannel: {self.datastore.channel}")
            return {}
        return await MessageSender(datastore=self.datastore).send_message_to_discord()

    async def _handling_errors(self, answer: dict) -> None:
        """Проверяет ошибки отправки сообщений"""

        if not answer:
            return
        if await self.__is_token_deleted():
            return
        await DBI.update_token_last_message_time(token=self.datastore.token)
        await self.__update_datastore_end_cooldown_time()
        await self.__check_datastore_new_delay()
        if answer.get("status") == 407:
            await self.__delete_workers_and_set_sleep_time()

    async def __delete_workers_and_set_sleep_time(self):
        """Удаляет всех работников и уходит на кулдаун канала текущего токена."""

        self.__workers = []
        await self.__set_delay_equal_channel_cooldown()
        logger.warning(
            f"\nUser: [{self.datastore.telegram_id}]"
            f"\nDeleting workers and sleep {self.delay} seconds."
        )

    async def __check_datastore_new_delay(self) -> None:
        """Проверяет изменился ли кулдаун и если изменился - меняет кулдаун
        пользовательского канала"""

        if self.datastore.new_delay <= self.datastore.delay:
            return
        new_cooldown: int = self.datastore.new_delay
        logger.warning(f"New cooldown set: "
                       f"\tChannel: {self.datastore.channel}"
                       f"\tCooldown: {new_cooldown}")
        await DBI.update_user_channel_cooldown(
            user_channel_pk=self.datastore.user_channel_pk, cooldown=new_cooldown)
        text = (
            "Для данного токена сообщения отправляются чаще, чем разрешено в канале."
            f"\nToken: {self.datastore.token}"
            f"\nГильдия/Канал: {self.datastore.guild}/{self.datastore.channel}"
            f"\nВремя скорректировано. Кулдаун установлен: {new_cooldown} секунд"
        )
        await self.message.answer(text)
        self.datastore.delay = new_cooldown
        await self.__delete_workers_and_set_sleep_time()

    @logger.catch
    async def __update_datastore_end_cooldown_time(self) -> None:
        """Обновляет время отката кулдауна токена"""

        self.datastore.update_end_cooldown_time(now=True)

    @logger.catch
    async def __set_delay_equal_channel_cooldown(self):
        """Устанавливает время для сна на величину кулдауна канала после корректировки"""

        self.delay = self.min_cooldown
        channel_data: namedtuple = await DBI.get_channel(self.datastore.user_channel_pk)
        if channel_data:
            self.delay = int(channel_data.cooldown)

    @check_working
    @logger.catch
    async def _make_working_data(self) -> None:
        """Создает пары токенов, список работников и следующий рабочий токен."""

        if not self.__workers:
            await self._make_token_pairs()
            await self._make_workers_list()
        await self._get_worker_from_list()

    @check_working
    @logger.catch
    async def _sleep(self) -> None:
        """Спит на время ближайшего токена."""

        if self.__workers:
            return
        self.min_cooldown: int = await self._get_minimal_channel_cooldown()
        self.delay: int = await self._get_delay()
        await self._send_delay_message()
        timer: int = self.delay
        while timer > 0:
            timer -= 5
            if not self.is_working:
                return
            await asyncio.sleep(5)
        self.delay = 0

    @check_working
    @logger.catch
    async def _make_workers_list(self) -> None:
        """Создает список токенов, которые не на КД"""

        self.__workers = [
            elem
            for elem in sorted(self._datastores_list, key=lambda x: x.end_cooldown_time)
            if get_current_timestamp() > elem.end_cooldown_time
        ]

    @check_working
    @logger.catch
    async def _get_worker_from_list(self) -> None:
        """Возвращает токен для работы"""

        if not self.__workers:
            return

        random.shuffle(self.__workers)
        self.datastore: 'TokenData' = self.__workers.pop(0)

    @logger.catch
    async def _get_delay(self) -> int:
        """Сохраняет время паузы взяв его из второго в очереди на работу токена"""

        if self.delay:  # Delay может быть уже задан в функции: _set_delay_equal_channel_cooldown
            return self.delay
        delay = await self.__get_cooldown()
        delay += random.randint(3, 7)
        logger.debug(f"User: {self._username}: {self._telegram_id}: Sleep delay = [{delay}]")

        return delay

    async def _get_minimal_channel_cooldown(self) -> int:
        """Возвращает минимальный кулдаун из всех существующих токенов пользователя"""

        return min(self._datastores_list, key=lambda x: x.cooldown).cooldown

    @check_working
    @logger.catch
    async def _send_delay_message(self) -> None:
        """Отправляет сообщение что все токены заняты"""

        if self.delay <= 0:
            return
        delay: int = self.delay
        text = "секунд"
        if delay > 60:
            minutes: int = delay // 60
            seconds: int = delay % 60
            if minutes < 10:
                minutes: str = f"0{minutes}"
            if seconds < 10:
                seconds: str = f'0{seconds}'
            delay: str = f"{minutes}:{seconds}"
            text = "минут"
        text: str = f"Все токены отработали. Следующий старт через {delay} {text}."
        logger.info(f"{self.message.from_user.username}: {self.message.from_user.id}: {text}")
        if not self.silence:
            await self.message.answer(text, reply_markup=in_work_keyboard())

    @check_working
    @logger.catch
    async def _send_replies(self) -> None:
        """Отправляет реплаи из дискорда в телеграм с кнопкой Ответить
        либо отправляет сообщение в нейросеть, чтоб она ответила"""

        replier: 'RepliesManager' = RepliesManager(self._telegram_id)
        data_for_reply: List[dict] = await replier.get_not_showed()
        for elem in data_for_reply:
            if self.auto_answer:
                await self._auto_reply_with_davinchi(elem, replier)
            else:
                await self.__send_reply_to_telegram(elem, replier)

    @logger.catch
    async def _auto_reply_with_davinchi(self, data: dict, replier: 'RepliesManager') -> None:
        """Отвечает с на реплай с помощью ИИ и сохраняет изменнные данные в Редис
        Если ИИ не ответил - отправляет сообщение пользователю в обычном режиме"""

        reply_text: str = data.get("text")
        ai_reply_text: str = await OpenAI(davinchi=False).get_answer(message=reply_text)
        if ai_reply_text:
            message_id: str = data.get("message_id")
            await replier.update_text(
                message_id=message_id, text=ai_reply_text)
            await replier.update_showed(message_id)
            text: str = await self.__get_message_text_from_dict(data)
            result: str = text + f"\nОтвет от ИИ: {ai_reply_text}"
            await self.message.answer(result, reply_markup=in_work_keyboard())
            return
        text: str = f"ИИ не ответил на реплай: [{reply_text}]"
        logger.warning(text)
        await self.message.answer(text, reply_markup=in_work_keyboard())
        await self.__send_reply_to_telegram(data, replier)

    @logger.catch
    async def __send_reply_to_telegram(self, data: dict, replier: 'RepliesManager') -> None:
        text: str = await self.__get_message_text_from_dict(data)
        message_id: str = data.get("message_id")
        await self.__reply_to_telegram(text=text, message_id=message_id)
        await replier.update_showed(data.get("message_id"))

    @logger.catch
    async def __get_message_text_from_dict(self, data) -> str:
        author: str = data.get("author")
        reply_text: str = data.get("text")
        reply_to_author: str = data.get("to_user")
        reply_to_message: str = data.get("to_message")
        return (
            f"Вам пришло сообщение из ДИСКОРДА:"
            f"\nКому: {reply_to_author}"
            f"\nНа сообщение: {reply_to_message}"
            f"\nОт: {author}"
            f"\nText: {reply_text}"
        )

    @logger.catch
    async def __reply_to_telegram(self, text: str, message_id: str) -> None:
        """Отправляет сообщение о реплае в телеграм"""

        answer_keyboard: 'InlineKeyboardMarkup' = InlineKeyboardMarkup(row_width=1)
        answer_keyboard.add(InlineKeyboardButton(
            text="Ответить",
            callback_data=f'reply_{message_id}'
        ))
        await self.message.answer(text, reply_markup=answer_keyboard)

    @check_working
    @logger.catch
    async def _make_token_pairs(self) -> None:
        """Очищает список работников и формирует новые пары"""

        self.__workers = []
        await DBI.delete_all_pairs(telegram_id=self._telegram_id)
        await self.__form_new_tokens_pairs()
        await self.__check_is_datastores_ready()

    @logger.catch
    async def __form_new_tokens_pairs(self) -> None:
        """Формирует пары токенов из свободных"""

        free_tokens: Tuple[
            List[namedtuple], ...] = await DBI.get_all_free_tokens(self._telegram_id)
        formed_pairs: int = 0
        sorted_tokens: Tuple[List[namedtuple], ...] = tuple(
            sorted(
                array, key=lambda x: x.last_message_time, reverse=True
            )
            for array in free_tokens
        )
        self._datastores_list = []
        self.total_tokens_count = 0
        for tokens_list in sorted_tokens:
            while len(tokens_list) > 1:
                first_token: namedtuple = tokens_list.pop()
                second_token: namedtuple = tokens_list.pop()
                formed_pairs += await DBI.make_tokens_pair(
                    first_token.token_pk, second_token.token_pk)
                datastores: List['TokenData'] = await self._create_datastore(
                    first_token, second_token)
                self._datastores_list.extend(datastores)
                self.total_tokens_count += 2

    @logger.catch
    async def __check_is_datastores_ready(self) -> None:
        """Проверяет количество токенов для работы бота, должно быть не меньше двух"""

        if len(self._datastores_list) < 2:
            text: str = "Недостаточно токенов для работы. Не смог сформировать ни одной пары"
            await self.message.answer(text)
            logger.error(text)
            self.is_working = False

    @logger.catch
    async def _create_datastore(self, data: Tuple[namedtuple, ...]) -> List['TokenData']:
        """Возвращает список экземпляров TokenData, созданных из данных о токенах."""

        return [await self.__create_datastore(data=elem) for elem in data]

    @logger.catch
    async def __create_datastore(self, data: namedtuple) -> 'TokenData':
        """Возвращает экземпляр TokenData, созданный из данных о токене."""

        datastore = TokenData(telegram_id=self._telegram_id)
        # TODO переписать после апдейта БД, вся информация должна быть уже в дате
        token_data: namedtuple = await DBI.get_info_by_token(token=data.token)
        datastore.update_data(
            token=data.token, token_data=token_data,
            last_message_time=data.last_message_time.timestamp(),
            token_pk=data.token_pk
        )
        return datastore

    @logger.catch
    async def __get_cooldown(self) -> int:
        """Возвращает время для сна"""

        token_with_min_end_time: 'TokenData' = min(
            self._datastores_list,
            key=lambda x: x.end_cooldown_time
        )
        first_end_time: int = int(token_with_min_end_time.end_cooldown_time)
        min_time: int = first_end_time - get_current_timestamp()
        logger.debug(
            f"\n\t\tTotal workers:\t {len(self.__workers)}"
            f"\n\t\tTotal datastore list:\t {len(self._datastores_list)}"
            f"\n\t\tToken with min time: {token_with_min_end_time.token}"
            f"\n\t\tFirst end time:\t {first_end_time}"
            f"\n\t\tCurrent time:  \t {get_current_timestamp()}"
            f"\n\t\tMin time: {min_time}"
        )
        return min_time
