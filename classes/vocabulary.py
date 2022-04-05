import random
import os

from config import logger


class Vocabulary:
    """Работает с файлом фраз для отправки в дискорд"""

    __VOCABULARY: list = []
    __PATH_TO_FILE: str = "./db/vocabulary_en.txt"

    @classmethod
    @logger.catch
    def get_message(cls) -> str:
        vocabulary: list = cls.__get_vocabulary()

        length: int = len(vocabulary)
        try:
            string_index: int = random.randint(0, length - 1)
            message_text: str = vocabulary.pop(string_index)
            cls.__set_vocabulary(vocabulary)
        except (ValueError, TypeError, FileNotFoundError) as err:
            logger.error(f"ERROR: __get_random_message_from_vocabulary: {err}")
            return "Vocabulary error"
        if len(message_text) > 60:
            return cls.get_message()
        return message_text

    @classmethod
    @logger.catch
    def __get_vocabulary(cls) -> list:
        if not cls.__VOCABULARY:
            cls.__update_vocabulary()

        return cls.__VOCABULARY

    @classmethod
    @logger.catch
    def __set_vocabulary(cls, vocabulary: list):
        if isinstance(vocabulary, list):
            if not vocabulary:
                cls.__update_vocabulary()
            else:
                cls.__VOCABULARY = vocabulary
        else:
            raise TypeError("__set_vocabulary error: ")

    @classmethod
    @logger.catch
    def __update_vocabulary(cls, file_name: str = None):
        if not file_name:
            file_name = cls.__PATH_TO_FILE
        if os.path.exists(file_name):
            with open(file_name, 'r', encoding='utf-8') as f:
                cls.__VOCABULARY = f.readlines()
        else:
            raise FileNotFoundError(f"__update_vocabulary: {file_name} error: ")
