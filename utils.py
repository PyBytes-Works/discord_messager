import os
import json
import random
import string

import aiogram
import aiogram.utils.exceptions
from aiogram.types import Message

from typing import Union
from config import logger, bot, admins_list
from keyboards import user_menu_keyboard


@logger.catch
def save_data_to_json(data, file_name: str = "data.json", key: str = 'w'):
    if key == 'w':
        with open(file_name, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    elif key == 'a':
        result = {}
        if os.path.exists(file_name):
            with open(file_name, 'r', encoding='utf-8') as f:
                result: dict = json.load(f)
        result.update(data)
        save_data_to_json(data=result, file_name=file_name, key='w')

    logger.debug(f"{file_name} saved.")


@logger.catch
def save_data_to_txt(data: Union[dict, list], file_name: str = "data.json"):
    with open(file_name, 'w', encoding='utf-8') as f:
        data = "\n".join(data)
        f.write(data)

    logger.debug(f"{file_name} saved.")


@logger.catch
def check_is_int(text: str) -> int:
    """Проверяет что в строке пришло положительное число и возвращает его обратно если да"""

    if text.isdigit():
        if int(text) > 0:
            return int(text)

    return 0


@logger.catch
def get_token(key: str) -> str:
    """Возвращает новый сгенерированный токен"""

    result = ''
    if key == "user":
        result = "new_user_"
    if key == "subscribe":
        result = "subscribe_"
    return result + ''.join(random.choices(string.ascii_letters, k=50))


@logger.catch
def add_new_token(tokens: dict) -> None:
    """Добавляет новый токен и имя, к которому он привязан, в файл"""

    if os.path.exists("tokens.json"):
        with open("tokens.json", 'r', encoding="utf-8") as f:
            old_tokens = json.load(f)
            if old_tokens:
                tokens.update(old_tokens)

    with open("tokens.json", 'w', encoding="utf-8") as f:
        json.dump(tokens, f, indent=4, ensure_ascii=False)


@logger.catch
def delete_used_token(token: str) -> dict:
    """Удаляет использованный токен из файла, возвращает имя пользователя"""

    user_data = {}
    tokens = {}
    if os.path.exists("tokens.json"):
        with open("tokens.json", "r", encoding="utf-8") as f:
            data = f.read().strip()
            if data:
                tokens = json.loads(data)
                if token in tokens:
                    user_data = tokens.pop(token)

    with open("tokens.json", "w", encoding="utf-8") as f:
        json.dump(tokens, f, indent=4, ensure_ascii=False)

    return user_data


@logger.catch
async def send_report_to_admins(text: str) -> None:
    """Отправляет сообщение в телеграме всем администраторам из списка"""

    text = f'[Рассылка][Superusers]: {text}'
    for admin_id in admins_list:
        try:
            await bot.send_message(chat_id=admin_id, text=text)
        except aiogram.utils.exceptions.ChatNotFound as err:
            logger.error(f"Не смог отправить сообщение пользователю {admin_id}.", err)


@logger.catch
async def errors_report(telegram_id: str, text: str) -> None:
    """Errors report"""

    logger.error(f"Errors report: {text}")
    await send_report_to_admins(text)
    await bot.send_message(chat_id=telegram_id, reply_markup=user_menu_keyboard())
