import os
import random
import time
from typing import Tuple

import openai

from config import logger

openai.api_key = os.getenv("OPEN_AI_KEY")


class OpenAI:

    def __init__(self, davinchi: bool = False):
        self.__message: str = ''
        self.__mode: str = "text-davinci-002" if davinchi else "text-curie-001"
        self.__counter: int = 0

    @logger.catch
    def __send_message(self) -> dict:
        time.sleep(0.5)
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

        self.__counter += 1
        plugs: Tuple[str, ...] = ('server here:', 'https://discord.gg/')
        defaults: Tuple[str, ...] = ('how are you', 'how are you doing')

        if self.__counter > 5:
            logger.warning(f"OpenAI counter: {self.__counter}")
            return random.choice(defaults)

        if not message:
            logger.warning("OpenAI: No message")
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
        if any(filter(lambda x: x in result, plugs)):
            return random.choice(defaults)
        if len(result) not in range(3, 101):
            return self.get_answer(message)
        return result


if __name__ == '__main__':
    def get_message_from_file() -> str:
        with open('../db/vocabulary_en.txt', 'r', encoding='utf-8') as f:
            data = f.readlines()
        return random.choice(data)


    messages = get_message_from_file().strip()
    bot = OpenAI()
    bot.get_answer(messages)
