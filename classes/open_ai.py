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
        time.sleep(2)
        try:
            response: dict = openai.Completion.create(
                engine=self.__mode,
                prompt=self.__message,
                temperature=0.6,
                # max_tokens=120,
                # top_p=0.5,
                # frequency_penalty=0.9,
                # presence_penalty=0.4,
                # stop=["You:"]
            )
        except openai.error.RateLimitError as err:
            logger.error(f"OpenAI: requests limit error: {err}")
            return {}
        except Exception as err:
            logger.error(f"OpenAI: EXCEPTION error: {err}")
            return {}
        return response

    @logger.catch
    def get_answer(self, message: str) -> str:
        """Returns answer from bot or empty string if errors"""

        logger.debug(f"\n\t\tOpenAI mode: {self.__mode}")

        self.__counter += 1
        logger.debug(f"№ {self.__counter} - Message for OpenAI: [{message.strip()}]")

        plugs: Tuple[str, ...] = ('server here:', 'https://discord.gg/', ".com", ".net", "www.", "http://", "https://")
        defaults: Tuple[str, ...] = ('how are you', 'how are you doing')

        if self.__counter > 5:
            logger.warning(f"OpenAI counter out of range: {self.__counter}"
                           f"\nMessage: {message}")
            return ''

        if not message:
            logger.warning("OpenAI: No message sent to OpenAI")
            return ''
        self.__message = message.strip()
        data: dict = self.__send_message()
        if not data:
            logger.error("\n\tOpenAI: No data\n")
            return ''
        answers: list = data.get("choices", [])

        if not answers:
            logger.error("\n\tOpenAI: No answers\n")
            return ''
        result: str = answers[0].get("text", '').strip().split("\n")[0]
        logger.debug(f"№ {self.__counter} - OpenAI answered: [{result}]")
        if result in (self._last_answer, message):
            return self.get_answer(message)
        self._last_answer = result
        if any(filter(lambda x: x in result, plugs)):
            logger.warning(f"\t\tOpenAI answer in plugs. Return default.")
            self.__counter -= 1
            return self.get_answer(message)
        if len(result) < MIN_MESSAGE_LENGTH:
            logger.warning(f"\t\tOpenAI answer not in range 3-100 symbols. Trying again.")
            return self.get_answer(message)
        if len(result) >= MAX_MESSAGE_LENGTH:
            result: str = result.split('.')[0]

        return result.lower()

    @staticmethod
    def get_message_from_file(filename: str = '') -> str:
        if not filename:
            filename: str = 'db/vocabulary_en.txt'
        with open(filename, 'r', encoding='utf-8') as f:
            data = f.readlines()
        return random.choice(data)


if __name__ == '__main__':
    # TODO отправить 10 асинхронных запросов с разным текстом вопроса
    # text = "sure you can definitely get what you want here, don't despair Keep communicating guys"
    text = "I’m in year 12, how you finding uni'"
    filename: str = '../db/vocabulary_en.txt'
    ai = OpenAI()
    print(ai.get_answer(message=ai.get_message_from_file(filename)))
    print(ai.get_answer(message=ai.get_message_from_file(filename)))
    print(ai.get_answer(message=ai.get_message_from_file(filename)))
    print(ai.get_answer(message=ai.get_message_from_file(filename)))
    print(ai.get_answer(message=ai.get_message_from_file(filename)))


