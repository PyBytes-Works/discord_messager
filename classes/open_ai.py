import os
import random
import time
from typing import Tuple

import openai

from config import logger

openai.api_key = os.getenv("OPEN_AI_KEY")
MIN_MESSAGE_LENGTH: int = 3
MAX_MESSAGE_LENGTH: int = 100


class OpenAI:

    def __init__(self, davinchi: bool = False):
        self.__message: str = ''
        self.__mode: str = "text-davinci-002" if davinchi else "text-curie-001"
        self.__counter: int = 0
        self._last_answer: str = ''

    @logger.catch
    def __send_message(self) -> dict:
        time.sleep(0.5)
        logger.debug(f"OpenAI mode: {self.__mode}")
        try:
            response: dict = openai.Completion.create(
                engine=self.__mode,
                prompt=self.__message,
                temperature=0.5,
                max_tokens=60,
                top_p=1.0,
                frequency_penalty=0.5,
                presence_penalty=0.0,
                stop=["You:"]
            )
        except openai.error.RateLimitError as err:
            logger.error(f"OpenAI: requests limit error: {err}")
            return {}
        except Exception as err:
            logger.error(f"OpenAI: EXCEPTION error: {err}")
            return {}
        return response

    @logger.catch
    def get_answer(self, message: str = '') -> str:
        """Returns answer from bot or empty string if errors"""

        self._last_answer = message
        self.__counter += 1
        logger.debug(f"№ {self.__counter} - Message to OpenAI: {message}")

        plugs: Tuple[str, ...] = ('server here:', 'https://discord.gg/')
        defaults: Tuple[str, ...] = ('how are you', 'how are you doing')

        if self.__counter > 5:
            logger.warning(f"OpenAI counter: {self.__counter}")
            return random.choice(defaults)

        if not message:
            logger.warning("OpenAI: No message sent to OpenAI")
            return ''
        self.__message = message.strip()
        data: dict = self.__send_message()
        if not data:
            logger.error("OpenAI: No data")
            return ''
        answers: list = data.get("choices", [])
        if not answers:
            logger.error("OpenAI: No answers")
            return ''
        result: str = answers[0].get("text", '').strip().split("\n")[0]
        if self._last_answer == result:
            message = self.get_message_from_file()
            return self.get_answer(message)
        self._last_answer = result
        logger.debug(f"№ {self.__counter} - OpenAI answered: {result}")
        if any(filter(lambda x: x in result, plugs)):
            logger.warning(f"\t\tOpenAI answer in plugs. Return default.")
            return random.choice(defaults)
        if len(result) not in range(MIN_MESSAGE_LENGTH, MAX_MESSAGE_LENGTH):
            logger.warning(f"\t\tOpenAI answer no in range 3-100. Repeat.")
            return self.get_answer(message)
        return result

    # TODO Если повторяется ответ от ИИ то взять случайное сообщение случайного пользователя из чата
    # и скормить его ИИ и ответить ему же реплаем

    @staticmethod
    def get_message_from_file() -> str:
        with open('db/vocabulary_en.txt', 'r', encoding='utf-8') as f:
            data = f.readlines()
        return random.choice(data)
