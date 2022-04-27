import datetime
import random
from typing import List, Optional, Tuple
from collections import namedtuple

import asyncio

from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from classes.message_receiver import MessageReceiver
from classes.message_sender import MessageSender
from classes.open_ai import OpenAI
from classes.replies import Replies
from classes.token_datastorage import TokenData

from config import logger
from keyboards import user_menu_keyboard
from classes.db_interface import DBI


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
    """Класс управления токенами и таймингами.
    Methods:
        lets_play
        form_token_pair
        is_expired_user_deactivated
    """

    def __init__(self, message: Message, mute: bool = False) -> None:
        self.message: 'Message' = message
        self.__username: str = message.from_user.username
        self.__telegram_id: str = str(self.message.from_user.id)
        self.__silence: bool = mute
        self.__related_tokens: List[namedtuple] = []
        self.__workers: List[str] = []
        self._datastore: Optional['TokenData'] = None
        self.is_working: bool = False
        self._discord_data: dict = {}
        self.delay: int = 0
        self.autoanswer: bool = False

    async def __get_full_info(self) -> str:
        return (
            f"\n\tUsername: {self.__username}"
            f"\n\tUser telegram id: {self.__telegram_id}"
            f"\n\tToken: {self._datastore.token}"
            f"\n\tProxy: {self._datastore.proxy}"
            f"\n\tDiscord ID: {self._datastore.my_discord_id}"
            f"\n\tMate discord id: {self._datastore.mate_id}"
            f"\n\tSilence: {self.__silence}"
            f"\n\tWorkers: {len(self.__workers)}/{len(self.__related_tokens)}"
            # f"\n\tRelated tokens: {self.__related_tokens}"
        )

    async def _check_user_active(self):
        user_deactivated: bool = await DBI.is_expired_user_deactivated(self.message)
        user_is_work: bool = await DBI.is_user_work(telegram_id=self.__telegram_id)
        if user_deactivated or not user_is_work:
            self.is_working = False

    @logger.catch
    async def _lets_play(self) -> None:

        await self._check_user_active()
        await self._get_worker()
        await self._getting_messages()
        await self._send_replies()
        await self._sending_messages()
        await self._sleep()

    @logger.catch
    async def __create_datastore(self) -> None:
        self._datastore: 'TokenData' = TokenData(self.__telegram_id)

    @logger.catch
    async def __make_all_token_ids(self) -> None:
        self._datastore.all_tokens_ids = await DBI.get_all_discord_id(self.__telegram_id)
        if not self._datastore.all_tokens_ids:
            logger.debug(f"No all_tokens_ids.")
            return
        self.is_working = True

    @logger.catch
    async def lets_play(self) -> None:
        """Show must go on
        Запускает рабочий цикл бота, проверяет ошибки."""

        # TODO Сделать флаг автоответа (если флаг стоит - то отвечает бот Давинчи, иначе -
        #  отправлять в телеграм юзеру

        # TODO разобраться с реплаями

        await self.__create_datastore()
        await self.__make_all_token_ids()
        logger.info(f"\n\tUSER: {self.__username}: {self.__telegram_id} - Game begin.")

        while self.is_working:
            t0 = datetime.datetime.now()
            # logger.debug(f"\n\t\tCircle start at: {t0}")
            await self._lets_play()

            # logger.debug(f"\n\t\tCircle finish. Total time: {datetime.datetime.now() - t0}")

        logger.info("\n\tGame over.")

    @check_working
    @logger.catch
    async def _getting_messages(self) -> None:
        """Получает сообщения из чата и обрабатывает их
        Если удачно - перезаписывает кулдаун текущего токена"""

        await MessageReceiver(datastore=self._datastore).get_message()
        await DBI.update_token_last_message_time(token=self._datastore.token)
        await self.__update_token_last_message_time(token=self._datastore.token)

    @logger.catch
    def __get_replaced_namedtuple(self, elem) -> namedtuple:
        return elem._replace(last_message_time=datetime.datetime.now())

    @logger.catch
    async def __update_token_last_message_time(self, token: str) -> None:
        """"""

        self.__related_tokens = [self.__get_replaced_namedtuple(elem)
                                 if elem.token == token else elem
                                 for elem in self.__related_tokens]

    @check_working
    @logger.catch
    async def _sending_messages(self) -> None:
        """Отправляет сообщение в дискор и сохраняет данные об ошибках в
        словарь атрибута класса"""

        if not await MessageSender(datastore=self._datastore).send_message():
            self.is_working = False
            return
        self._discord_data = {}
        self._datastore.current_message_id = 0

    @logger.catch
    async def __send_text(self, text: str, keyboard=None, check_silence: bool = False) -> None:
        """Отправляет текст и клавиатуру пользователю если он не в
        тихом режиме."""

        if check_silence and self.__silence:
            return
        if not keyboard:
            await self.message.answer(text)
            return
        await self.message.answer(text, reply_markup=keyboard)

    @check_working
    @logger.catch
    async def _get_worker(self) -> None:

        if not self.__workers:
            await self.make_token_pairs(unpair=True)
            await self._make_workers_list()
        logger.info(await self.__get_full_info())
        await self._get_worker_from_list()

    @check_working
    @logger.catch
    async def _sleep(self) -> None:
        """Спит на время ближайшего токена."""

        if self.__workers:
            return
        await self._get_delay()
        self.delay += random.randint(3, 7)
        logger.info(f"SLEEP PAUSE: {self.delay}")
        await self._send_delay_message()
        timer: int = self.delay
        while timer > 0:
            timer -= 5
            if not self.is_working:
                return
            await asyncio.sleep(5)

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
    def __get_current_timestamp(self) -> int:
        """Возвращает текущее время (timestamp) целое."""

        return int(datetime.datetime.now().timestamp())

    @logger.catch
    async def _update_datastore(self, token: str) -> None:
        token_data: namedtuple = await DBI.get_info_by_token(token)
        self._datastore.update_data(token=token, token_data=token_data)

    @logger.catch
    async def __get_closest_token_time(self) -> namedtuple:
        # return await DBI.get_closest_token_time(self._datastore.telegram_id)
        return sorted(self.__related_tokens, key=lambda x: x.last_message_time)[1]

    @logger.catch
    async def _get_delay(self) -> None:
        token_data: namedtuple = await self.__get_closest_token_time()
        message_time: int = int(token_data.last_message_time.timestamp())
        cooldown: int = token_data.cooldown
        self.delay = cooldown - abs(message_time - self.__get_current_timestamp())

    @check_working
    @logger.catch
    async def _send_delay_message(self) -> None:
        """Отправляет сообщение что все токены заняты"""

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
            await self.__send_text(text=text, check_silence=True)

    @check_working
    @logger.catch
    async def _send_replies(self) -> None:
        """Отправляет реплаи из дискорда в телеграм с кнопкой Ответить"""

        # TODO реализовать автоответчик
        # result_replies: List[dict] = []
        for elem in self._datastore.for_reply:
            if not elem.get("showed"):
                # if self.autoanswer:
                #     result_replies.append(await self._auto_reply_with_davinchi(reply))
                # else:
                await self.__reply_to_telegram(elem)
                await Replies(self.__telegram_id).update_showed(str(elem.get("message_id")))
                # result_replies.append(reply)
        # if self.autoanswer:
        #     await RedisDB(redis_key=self._datastore.telegram_id).save(data=result_replies)

    @logger.catch
    async def __reply_to_telegram(self, data: dict) -> None:
        """Отправляет сообщение о реплае в телеграм"""

        answer_keyboard: 'InlineKeyboardMarkup' = InlineKeyboardMarkup(row_width=1)
        author: str = data.get("author")
        reply_id: str = data.get("message_id")
        reply_text: str = data.get("text")
        reply_to_author: str = data.get("to_user")
        reply_to_message: str = data.get("to_message")
        answer_keyboard.add(InlineKeyboardButton(
            text="Ответить",
            callback_data=f'reply_{reply_id}'
        ))
        await self.message.answer(
            f"Вам пришло сообщение из ДИСКОРДА:"
            f"\nКому: {reply_to_author}"
            f"\nНа сообщение: {reply_to_message}"
            f"\nОт: {author}"
            f"\nText: {reply_text}",
            reply_markup=answer_keyboard
        )

    @logger.catch
    async def _auto_reply_with_davinchi(self, data: dict) -> dict:

        logger.debug("Start autoreply:")
        reply_text: str = data.get("text")
        ai_reply_text: str = OpenAI(davinchi=True).get_answer(message=reply_text)
        logger.debug(f"Davinci text: {ai_reply_text}")
        if not ai_reply_text:
            logger.error(f"Davinci NOT ANSWERED")
            return data
        data.update({"answer_text": ai_reply_text})
        return data

    @check_working
    @logger.catch
    async def make_token_pairs(self, unpair: bool = False) -> None:
        """Формирует пары из свободных токенов если они в одном канале"""

        if unpair:
            await DBI.delete_all_pairs(telegram_id=self.__telegram_id)
        await self.form_new_tokens_pairs()

    @logger.catch
    async def form_new_tokens_pairs(self) -> None:
        """Формирует пары токенов из свободных"""

        free_tokens: Tuple[List[namedtuple], ...] = await DBI.get_all_free_tokens(self.__telegram_id)
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
                first_token = tokens.pop()
                second_token = tokens.pop()
                # logger.debug(f"\n\tPaired tokens: {first_token.token_pk} + {second_token.token_pk}")
                formed_pairs += await DBI.make_tokens_pair(first_token.token_pk, second_token.token_pk)
                self.__related_tokens.append(first_token)
                self.__related_tokens.append(second_token)
        if not self.__related_tokens:
            await self.__send_text(
                text="Не смог сформировать пары токенов.",
                keyboard=user_menu_keyboard())
            self.is_working = False

    @property
    def silence(self) -> bool:
        return self.__silence

    @silence.setter
    def silence(self, silence: bool):
        if not isinstance(silence, bool):
            raise TypeError("Silence must be boolean.")
        self.__silence = silence
