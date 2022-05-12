import datetime
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

from config import logger
from classes.db_interface import DBI
from keyboards import user_menu_keyboard, in_work_keyboard


def check_working(func):
    async def wrapper(*args, **kwargs):
        name: str = func.__name__
        if args and hasattr(args[0].__class__, name):
            is_working: bool = getattr(args[0], "is_working")
            if is_working:
                # logger.debug(f"\t{name}: OK")
                return await func(*args, **kwargs)
        # logger.debug(f"\t{name}: FAIL")
        return

    return wrapper


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
        self.__telegram_id: str = str(self.message.from_user.id)
        self.datastore: Optional['TokenData'] = TokenData(self.__telegram_id)
        self.delay: int = 0
        self.is_working: bool = False
        self.auto_answer: bool = False
        self.reboot: bool = False
        self.silence: bool = False
        self.__username: str = message.from_user.username
        self.__related_tokens: List[namedtuple] = []
        self.__workers: List[str] = []

    @logger.catch
    async def lets_play(self) -> None:
        """Show must go on
        Запускает рабочий цикл бота, проверяет ошибки."""

        logger.info(f"\n\tUSER: {self.__username}: {self.__telegram_id} - Game begin.")
        # TODO перенести в MessageManager class
        await self._make_all_token_ids()

        while self.is_working:
            await self._lets_play()
        logger.info(f"\n\tUSER: {self.__username}: {self.__telegram_id} - Game over.")

    @check_working
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
            f"\n\tUsername: {self.__username}"
            f"\n\tUser telegram id: {self.__telegram_id}"
            f"\n\tToken: {self.datastore.token}"
            f"\n\tProxy: {self.datastore.proxy}"
            f"\n\tDiscord ID: {self.datastore.my_discord_id}"
            f"\n\tMate discord id: {self.datastore.mate_id}"
            f"\n\tSilence: {self.silence}"
            f"\n\tAutoanswer: {self.auto_answer}"
            f"\n\tWorkers: {len(self.__workers)}/{len(self.__related_tokens)}"
            f"\n\tDelay: {self.delay}"
        )

    async def _check_user_active(self):
        user_deactivated: bool = await DBI.is_expired_user_deactivated(self.message)
        user_is_work: bool = await DBI.is_user_work(telegram_id=self.__telegram_id)
        if user_deactivated or not user_is_work:
            await self.message.answer(
                "Работа завершена - пользователь не работает или деактивирован")
            self.is_working = False

    @logger.catch
    async def _lets_play(self) -> None:
        # TODO сделать декоратор из reboot
        await self.__check_reboot()
        await self._check_user_active()
        await self._make_working_data()
        await self._handling_received_messages()
        await asyncio.sleep(3)
        await self._send_replies()
        await asyncio.sleep(3)
        await self._sending_messages()
        await self._sleep()

    @logger.catch
    async def _make_all_token_ids(self) -> None:
        """Получает дискорд ИД всех токенов пользователя. Если их больше двух -
        начинает работу, иначе - завершает."""

        self.datastore.all_tokens_ids = await DBI.get_all_discord_id(self.__telegram_id)
        if len(self.datastore.all_tokens_ids) < 2:
            logger.debug(f"_make_all_token_ids ERROR: Not enough all_tokens_ids.")
            await self.message.answer("Нужно добавить минимум два токена в один канал для работы.")
            self.is_working = False
            return
        self.is_working = True

    @check_working
    @logger.catch
    async def _handling_received_messages(self) -> None:
        """Получает сообщения из чата и обрабатывает их"""

        if not all((self.datastore.token, self.datastore.channel)):
            logger.error(f"\nError: TG: {self.datastore.telegram_id}"
                         f"\nToken: {self.datastore.token}"
                         f"\nChannel: {self.datastore.channel}")
            return
        await MessageManager(datastore=self.datastore).handling_messages()

    @logger.catch
    def __replace_time_to_now(self, elem) -> namedtuple:
        return elem._replace(last_message_time=datetime.datetime.now())

    @logger.catch
    async def __update_token_last_message_time(self, token: str) -> None:
        """"""

        self.__related_tokens = [self.__replace_time_to_now(elem)
                                 if elem.token == token else elem
                                 for elem in self.__related_tokens]

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
        await DBI.update_token_last_message_time(token=self.datastore.token)
        await self.__update_token_last_message_time(token=self.datastore.token)
        status = answer.get("status")
        if status == 200:
            return
        elif status == 407:
            await self._set_delay_and_delete_all_workers()
        elif status == 429:
            code: int = answer.get("answer_data").get("code")
            if code == 20016:
                await self._set_delay_and_delete_all_workers()
            elif code == 40062:
                await self._set_delay_and_delete_all_workers()
                await self.form_new_tokens_pairs()
        if self.delay:
            logger.warning(
                f"\nError [{answer}]"
                f"\nUser: [{self.datastore.telegram_id}]"
                f"\nDeleting workers and sleep {self.delay} seconds.")

    @logger.catch
    async def _set_delay_and_delete_all_workers(self):
        self.__workers = []
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

        logger.debug(await self.__get_full_info())
        if self.__workers:
            return
        await self._get_delay()
        self.delay += random.randint(3, 7)
        logger.debug(f"\n\t\tSelf.delay: {self.delay}")
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

        return int(elem.last_message_time.timestamp()) + elem.cooldown

    @check_working
    @logger.catch
    async def _make_workers_list(self) -> None:
        """Возвращает список токенов, которые не на КД"""

        self.__workers = [
            elem.token
            for elem in self.__related_tokens
            if self.__get_current_timestamp() > self.__get_max_message_time(elem)
        ]

    @check_working
    @logger.catch
    async def _get_worker_from_list(self) -> None:
        """Возвращает токен для работы"""

        if not self.__workers:
            return
        random.shuffle(self.__workers)
        random_token: str = self.__workers.pop()
        await self._update_datastore(random_token)

    @logger.catch
    async def _update_datastore(self, token: str) -> None:
        """Обновляет данные datastore информацией о токене, полученной из БД"""

        token_data: namedtuple = await DBI.get_info_by_token(token)
        self.datastore.update_data(token=token, token_data=token_data)

    @logger.catch
    def __get_current_timestamp(self) -> int:
        """Возвращает текущее время (timestamp) целое."""

        return int(datetime.datetime.now().timestamp())

    @logger.catch
    async def __get_second_closest_token_time(self) -> namedtuple:
        """Возвращает время второго ближайшего токена"""

        return sorted(self.__related_tokens, key=lambda x: x.last_message_time)[1]

    @logger.catch
    async def _get_delay(self) -> None:
        """Сохраняет время паузы взяв его из второго в очереди на работу токена"""

        if self.delay:
            return
        token_data: namedtuple = await self.__get_second_closest_token_time()
        message_time: int = int(token_data.last_message_time.timestamp())
        cooldown: int = token_data.cooldown
        self.delay = cooldown + message_time - self.__get_current_timestamp()

    @check_working
    @logger.catch
    async def _send_delay_message(self) -> None:
        """Отправляет сообщение что все токены заняты"""

        logger.info(f"{self.__telegram_id}: SLEEP PAUSE: {self.delay}")
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
        if not self.silence:
            await self.message.answer(text, reply_markup=in_work_keyboard())

    @check_working
    @logger.catch
    async def _send_replies(self) -> None:
        """Отправляет реплаи из дискорда в телеграм с кнопкой Ответить
        либо отправляет сообщение в нейросеть, чтоб она ответила"""

        replier: 'RepliesManager' = RepliesManager(self.__telegram_id)
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
        ai_reply_text: str = OpenAI(davinchi=False).get_answer(message=reply_text)
        if ai_reply_text:
            message_id: str = data.get("message_id")
            await replier.update_text(
                message_id=message_id, text=ai_reply_text)
            await replier.update_showed(message_id)
            text: str = await self.__get_message_text_from_dict(data)
            result: str = text + f"\nОтвет от ИИ: {ai_reply_text}"
            await self.message.answer(result, reply_markup=in_work_keyboard())
            return
        logger.error(f"Davinci NOT ANSWERED to:"
                     f"\n{reply_text}")
        text: str = ("ИИ не ответил на реплай: "
                     f"\n{reply_text}")
        await self.message.answer(text, reply_markup=in_work_keyboard())
        # await ErrorsReporter.send_report_to_admins(text)
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

        await DBI.delete_all_pairs(telegram_id=self.__telegram_id)
        await self.form_new_tokens_pairs()

    @logger.catch
    async def form_new_tokens_pairs(self) -> None:
        """Формирует пары токенов из свободных"""

        free_tokens: Tuple[
            List[namedtuple], ...] = await DBI.get_all_free_tokens(self.__telegram_id)
        formed_pairs: int = 0
        sorted_tokens: Tuple[List[namedtuple], ...] = tuple(
            sorted(
                array, key=lambda x: x.last_message_time, reverse=True
            )
            for array in free_tokens
        )
        self.__related_tokens = []
        for tokens in sorted_tokens:
            while len(tokens) > 1:
                first_token: namedtuple = tokens.pop()
                second_token: namedtuple = tokens.pop()
                formed_pairs += await DBI.make_tokens_pair(
                    first_token.token_pk, second_token.token_pk)
                self.__related_tokens.append(first_token)
                self.__related_tokens.append(second_token)
        if len(self.__related_tokens) < 2:
            await self.message.answer(
                "Недостаточно токенов для работы. Не смог сформировать ни одной пары")
            logger.error(f"\n\nTotal tokens: {len(free_tokens)}"
                         f"\nTokens: {free_tokens}\n")
            self.is_working = False
