import asyncio
import random

from classes.db_interface import DBI
from classes.errors_sender import ErrorsSender
from classes.open_ai import OpenAI
from classes.redis_interface import RedisDB
from classes.request_classes import PostRequest
from classes.vocabulary import Vocabulary
from config import logger, DISCORD_BASE_URL
from classes.token_datastorage import TokenData


class MessageSender(PostRequest):
    """Отправляет сообщение в дискорд-канал в ответ на сообщение
    связанного токена
    Возвращает сообщение об ошибке или об успехе"""

    def __init__(self, datastore: 'TokenData'):
        super().__init__()
        self._datastore: 'TokenData' = datastore
        self.__text: str = ''

    @logger.catch
    async def send_message_to_discord(self) -> bool:
        """Отправляет данные в канал дискорда, возвращает результат отправки."""

        self.__text = self._datastore.text_to_send
        await self.__prepare_data()
        if self._datastore.data_for_send:
            return await self.__send_data()

    async def _typing(self) -> None:
        """Имитирует "Пользователь печатает" в чате дискорда."""

        self.url = f'https://discord.com/api/v9/channels/{self._datastore.channel}/typing'
        answer: dict = await self._send_request()
        if answer.get("status") not in range(200, 205):
            logger.warning(f"Typing: {answer}")
        await asyncio.sleep(2)

    async def __send_data(self) -> bool:
        """
        Sends data to discord channel
        :return:
        """
        self.token = self._datastore.token
        self.proxy = self._datastore.proxy
        self._data_for_send = self._datastore.data_for_send

        await self._typing()
        await self._typing()
        self.url = DISCORD_BASE_URL + f'{self._datastore.channel}/messages?'

        logger.debug("MessageSender.__send_data::"
                     f"\nParams: "
                     f"\n\tToken: {self.token}"
                     f"\n\tProxy:{self.proxy}"
                     f"\n\tChannel: {self._datastore.channel}"
                     f"\n\tData for send: {self._data_for_send}")

        answer: dict = await self._send_request()
        status: int = answer.get("status")
        if status == 200:
            return True
        self._update_err_params(answer=answer, datastore=self._datastore)
        result: dict = await ErrorsSender(**self._error_params).handle_errors()

        data: dict = result.get('answer_data', {})
        code: int = data.get("code")
        if status == 429 and code == 20016:
            # cooldown: int = int(data.get("retry_after"))
            # if cooldown:
            #     cooldown += self._datastore.cooldown
            #     await DBI.update_user_channel_cooldown(
            #         user_channel_pk=self._datastore.user_channel_pk, cooldown=cooldown)
            #     self._datastore.delay = cooldown
            # await ErrorsSender(telegram_id=self._datastore.telegram_id).errors_report(
            #     text=(
            #         "Для данного токена сообщения отправляются чаще, чем разрешено в канале."
            #         f"\nToken: {self._datastore.token}"
            #         f"\nГильдия/Канал: {self._datastore.guild}/{self._datastore.channel}"
            #         f"\nВремя скорректировано. Кулдаун установлен: {cooldown} секунд"
            #     )
            # )
            return True

    @logger.catch
    async def __get_text_from_vocabulary(self) -> str:
        text: str = Vocabulary.get_message()
        if not text:
            await ErrorsSender.send_report_to_admins(text="Ошибка словаря фраз.")
            return ''
        await RedisDB(redis_key=self._datastore.mate_id).save(data=[
            text], timeout_sec=self._datastore.delay + 300)
        return text

    @logger.catch
    async def __prepare_message_text(self) -> None:
        mate_message: list = await RedisDB(redis_key=self._datastore.my_discord_id).load()
        if mate_message:
            self.__text: str = OpenAI().get_answer(mate_message[0].strip())
            if self._fifty_fifty():
                logger.debug("50 / 50 You got it!!!")
                self._datastore.current_message_id = 0
            await RedisDB(
                redis_key=self._datastore.my_discord_id).delete(mate_id=self._datastore.mate_id)
            return
        if self._ten_from_hundred():
            logger.debug("Random message! You are lucky!!!")
            self._datastore.current_message_id = 0
        self.__text: str = await self.__get_text_from_vocabulary()

    @logger.catch
    async def __get_text(self) -> None:
        if self.__text:
            return
        await self.__prepare_message_text()

    @logger.catch
    async def __prepare_data(self) -> None:
        """Возвращает сформированные данные для отправки в дискорд"""

        await self.__get_text()
        if not self.__text:
            logger.warning("Message sender.__prepare_data: no text for sending.")
            return
        self._datastore.data_for_send = {
            "content": self.__text,
            "tts": "false"
        }
        if self._datastore.current_message_id:
            params: dict = {
                "message_reference":
                    {
                        "guild_id": self._datastore.guild,
                        "channel_id": self._datastore.channel,
                        "message_id": self._datastore.current_message_id
                    },
                "allowed_mentions":
                    {
                        "parse": [
                            "users",
                            "roles",
                            "everyone"
                        ],
                        "replied_user": "false"
                    }
            }
            self._datastore.data_for_send.update(**params)

    @staticmethod
    @logger.catch
    def _ten_from_hundred() -> bool:
        return random.randint(1, 100) <= 10

    @staticmethod
    @logger.catch
    def _fifty_fifty() -> bool:
        return random.randint(1, 100) <= 50
