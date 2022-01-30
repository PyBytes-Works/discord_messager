import json
import os
import random
import string

from typing import Union
from config import logger, bot, admins_list


def save_data_to_json(data, file_name: str = "data.json"):
    with open(file_name, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    # print(file_name, "saved.")


def save_data_to_txt(data: Union[dict, list], file_name: str = "data.json"):
    with open(file_name, 'w', encoding='utf-8') as f:
        data = "\n".join(data)
        f.write(data)

    print(file_name, "saved.")


def str_to_int(text: str) -> int:
    """
    перевод строки в число
    если что не так вернёт None
    """
    if text.isdecimal():
        try:
            return int(text)
        except ValueError as exc:
            pass


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
def delete_used_token(token: str) -> str:
    """Удаляет использованный токен из файла, возвращает имя пользователя"""

    user_name = ''
    tokens = {}
    if os.path.exists("tokens.json"):
        with open("tokens.json", "r", encoding="utf-8") as f:
            data = f.read().strip()
            if data:
                tokens = json.loads(data)
                if token in tokens:
                    user_name = tokens.pop(token)

    with open("tokens.json", "w", encoding="utf-8") as f:
        json.dump(tokens, f, indent=4, ensure_ascii=False)

    return user_name


async def send_report_to_admins(text: str) -> None:
    """Отправляет сообщение в телеграме всем администраторам из списка"""

    for admin_id in admins_list:
        await bot.send_message(chat_id=admin_id, text=text)
