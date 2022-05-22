import datetime
import random
from typing import List, Optional, Tuple
from collections import namedtuple

import asyncio

from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from classes.errors_reporter import ErrorsReporter
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
        # self.__related_tokens: List[namedtuple] = []
        self.__workers: List[str] = []
        self.__all_user_tokens_discord_ids: List[str] = []
        self.__token_work_time: int = 10
        self.channels_list: List[List[namedtuple]] = []

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

        # TODO сделать декоратор из reboot
        await self.__check_reboot()
        await self._check_user_active()
        await self._make_working_data()
        async with self.semaphore:
            await self._handling_received_messages()
            await self._send_replies()
            await self._sending_messages()
        await self._sleep()

    @logger.catch
    async def __check_reboot(self) -> None:
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
            # f"\n\tWorkers: {len(self.__workers)}/{len(self.__related_tokens)}"
            f"\n\tDelay: {self.delay}"
            f"\n\tTokens cooldowns:\n\t\t"
            #         + '\n\t\t'.join(
            #     f"PK: {elem.token_pk}\tCD:{elem.cooldown}\tLMT: {elem.last_message_time}"
            #     f"\tTIME: {get_current_time()}\tCHN: {elem.channel_id}"
            #     f"\tDELAY: {get_current_timestamp() + elem.cooldown - elem.last_message_time.timestamp()}"
            #     for elem in self.__related_tokens
            # )
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
        total_tokens: List[namedtuple] = [
            elem
            for tokens in self.channels_list
            for elem in tokens
        ]
        self.datastore.token_time_delta = (
                (len(total_tokens) - len(self.__workers))
                * self.__token_work_time
        )
        # self.datastore.token_time_delta = (
        #         (len(self.__related_tokens) - len(self.__workers))
        #         * self.__token_work_time
        # )
        logger.debug(f"{self.datastore.token_time_delta=}")
        await MessageManager(datastore=self.datastore).handling_messages()
        await self.__is_token_deleted()

    @logger.catch
    def _replace_time_to_now(self, elem: namedtuple) -> namedtuple:
        return elem._replace(last_message_time=datetime.datetime.utcnow().replace(tzinfo=None))

    # @logger.catch
    # async def __update_token_last_message_time(self, token: str) -> None:
    #     """"""
    #
    #     self.__related_tokens = [self._replace_time_to_now(elem)
    #                              if elem.token == token else elem
    #                              for elem in self.__related_tokens]

    @logger.catch
    async def __is_token_deleted(self) -> bool:
        if self.datastore.token == 'deleted':
            await self._make_token_pairs()
            return True
        return False

    @check_working
    @logger.catch
    async def _sending_messages(self) -> None:
        """Отправляет сообщение в дискорд"""

        if not all((self.datastore.token, self.datastore.channel)):
            logger.error(f"\nError: TG: {self.datastore.telegram_id}"
                         f"\nToken: {self.datastore.token}"
                         f"\nChannel: {self.datastore.channel}")
            return
        answer: dict = await MessageSender(datastore=self.datastore).send_message_to_discord()
        if await self.__is_token_deleted():
            return
        await DBI.update_token_last_message_time(token=self.datastore.token)
        # await self.__update_token_last_message_time(token=self.datastore.token)
        self.__new_update_token_last_message_time(token=self.datastore.token)
        status = answer.get("status")
        if status == 200:
            return
        elif status in (407, 429):
            self.__workers = []
            await self._set_delay_equal_channel_cooldown()
        logger.warning(
            f"\nUser: [{self.datastore.telegram_id}]"
            f"\nDeleting workers and sleep {self.delay} seconds."
            f"\nError [{answer}]"
        )

    @logger.catch
    async def _set_delay_equal_channel_cooldown(self):
        self.delay = 60
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

        # logger.debug(await self.__get_full_info())
        if self.__workers:
            return
        await self._get_delay()
        self.delay += random.randint(0, 7)
        logger.debug(f"User: {self._username}: {self._telegram_id}: Sleep delay = [{self.delay}]")
        await self._send_delay_message()
        timer: int = self.delay
        while timer > 0:
            timer -= 5
            if not self.is_working:
                return
            await asyncio.sleep(5)
        self.delay = 0

    @logger.catch
    def __get_max_message_time(self, elem: namedtuple) -> int:
        """Возвращает максимальное время фильтрации сообщения. Сообщения с временем меньше
        данного будут отфильтрованы"""
        res = int(elem.last_message_time.timestamp()) + elem.cooldown
        # logger.debug(
        #     f"\nToken: [{elem.token_pk}]"
        #     f"\n{get_current_timestamp()} - {res} = {get_current_timestamp() - res}"
        # )
        return res

    @check_working
    @logger.catch
    async def _make_workers_list(self) -> None:
        """Создает список токенов, которые не на КД"""

        # for elem in sorted(self.__related_tokens, key=lambda x: x.last_message_time.timestamp()):
        #     logger.warning(f"\nCur time: {get_current_timestamp()}"
        #                    f"\nMax time: {self.__get_max_message_time(elem)}")
        #     if get_current_timestamp() > self.__get_max_message_time(elem):
        #         self.__workers.append(elem.token.strip())
        # TODO копию может быть?
        # self.__workers = [
        #     elem.token.strip()
        #     for elem in sorted(self.__related_tokens, key=lambda x: x.last_message_time.timestamp())
        #     if get_current_timestamp() > self.__get_max_message_time(elem)
        # ]
        # IN TESTING
        self.__workers = await self.__get_workers_list_from_channels_list()

    @check_working
    @logger.catch
    async def _get_worker_from_list(self) -> None:
        """Возвращает токен для работы"""

        # logger.debug(
        #     f"\nRelated tokens: [{len(self.__related_tokens)}]"
        #     f"\nWorkers: [{len(self.__workers)}]"
        # )
        if not self.__workers:
            return

        random.shuffle(self.__workers)
        random_token: str = self.__workers.pop()
        # logger.debug(f"\nWorker selected: {random_token}")
        await self._update_datastore(random_token)

    @logger.catch
    async def _update_datastore(self, token: str) -> None:
        """Обновляет данные datastore информацией о токене, полученной из БД"""

        token_data: namedtuple = await DBI.get_info_by_token(token)
        # TODO выяснить почему???
        if not token_data:
            self.datastore.token = 'deleted'
            await self.__is_token_deleted()
            error_text: str = (
                f'NOT TOKEN DATA FOR TOKEN: {token}'
                f'\nToken_data: {token_data}'
                f'\nTelegram_id: {self.datastore.telegram_id}'
                f'\nChannel: {self.datastore.channel}'
                f'\nWorkers: {self.__workers}'
            )
            await ErrorsReporter.send_message_to_user(telegram_id="305353027", text=error_text)
            logger.error(error_text)
            await self.__get_full_info()
            # self.is_working = False
            return
        self.datastore.update_data(token=token, token_data=token_data)
        self.datastore.all_tokens_ids = self.__all_user_tokens_discord_ids

    # @logger.catch
    # async def __get_last_token_time(self) -> namedtuple:
    #     """Возвращает время второго ближайшего токена"""
    #
    #     return sorted(
    #         self.__related_tokens,
    #         key=lambda x: x.last_message_time.timestamp() + x.cooldown
    #     )[-1]

    @logger.catch
    async def _get_delay(self) -> None:
        """Сохраняет время паузы взяв его из второго в очереди на работу токена"""

        if self.delay:  # Delay может быть уже задан в функции: _set_delay_equal_channel_cooldown
            return
        # token_data: namedtuple = await self.__get_last_token_time()
        # message_time: int = int(token_data.last_message_time.timestamp())
        # cooldown: int = token_data.cooldown
        # self.delay = cooldown + message_time - get_current_timestamp()
        self.delay = self.__get_cooldown()

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
        """Формирует пары из свободных токенов если они в одном канале"""

        self.__workers = []
        await DBI.delete_all_pairs(telegram_id=self._telegram_id)
        await self.__form_new_tokens_pairs()

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
        # self.__related_tokens = []
        self.channels_list = []
        for tokens_list in sorted_tokens:
            channel_list = []
            while len(tokens_list) > 1:
                first_token: namedtuple = tokens_list.pop()
                second_token: namedtuple = tokens_list.pop()
                formed_pairs += await DBI.make_tokens_pair(
                    first_token.token_pk, second_token.token_pk)
                # self.__related_tokens.append(first_token)
                # self.__related_tokens.append(second_token)
                # IN TESTING
                channel_list.append(first_token)
                channel_list.append(second_token)
            if len(channel_list) > 1:
                self.channels_list.append(channel_list)
                # *****
        # if len(self.__related_tokens) < 2:
        #     await self.message.answer(
        #         "Недостаточно токенов для работы. Не смог сформировать ни одной пары")
        #     logger.error(f"\n\nTotal tokens: {len(free_tokens)}"
        #                  f"\nTokens: {free_tokens}\n")
        #     self.is_working = False

        # IN TESTING
        if not self.channels_list:
            await self.message.answer(
                "Недостаточно токенов для работы. Не смог сформировать ни одной пары")
            logger.error(f"\n\nNEW Total tokens: {len(free_tokens)}"
                         f"\nNEW Tokens: {free_tokens}\n")
            self.is_working = False

    # IN TESTING!!! *************************

    async def __get_workers_list_from_channels_list(self) -> List[str]:
        workers = []
        for tokens_list in self.channels_list:
            channel_workers: List[str] = self.__get_workers_from_tokens_list(tokens_list)
            if len(channel_workers) > 1:
                workers.extend(channel_workers)

        min_delay: int = self.__get_cooldown()
        logger.warning(
            f"\nNew channels list: [{len(self.channels_list)}]:"
            f"\n{self.channels_list}"
            f"\nNew workers: [{len(workers)}]"
            f"\n{workers}"
            f"\nNew {min_delay=}"
        )
        return workers

    def __get_workers_from_tokens_list(self, tokens_list: List[namedtuple]) -> List[str]:
        return [
            elem.token.strip()
            for elem in sorted(tokens_list, key=lambda x: x.last_message_time.timestamp())
            if get_current_timestamp() > self.__get_max_message_time(elem)
        ]

    def __get_cooldown(self) -> int:
        token_data: namedtuple = min(
            map(lambda x: self.__get_last_time_token(x), self.channels_list),
            key=lambda x: x.last_message_time.timestamp()
        )
        logger.warning(f"\n{token_data=}")
        message_time: int = int(token_data.last_message_time.timestamp())
        cooldown: int = token_data.cooldown
        min_time: int = cooldown + message_time - get_current_timestamp()

        return min_time

    @staticmethod
    def __get_last_time_token(data: List[namedtuple]) -> namedtuple:
        return sorted(
            data,
            key=lambda x: x.last_message_time.timestamp() + x.cooldown
        )[-1]

    def __new_update_token_last_message_time(self, token: str):
        self.channels_list = [
            [
                self._replace_time_to_now(elem)
                if elem.token == token else elem
                for elem in tokens
            ]
            for tokens in self.channels_list
        ]
