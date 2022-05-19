import datetime
import os
import json

from typing import Union
from config import logger, DEBUG, SAVING


@logger.catch
def save_data_to_json(data: Union[dict, list], file_name: str = "data.json", key: str = 'w'):
    folder_for_saving = 'logs/saved_files'
    if not os.path.exists(folder_for_saving):
        os.mkdir(folder_for_saving)
    path: str = f"{folder_for_saving}/{file_name}"
    if key == 'w':
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    elif key == 'a':
        result = {}
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                result: dict = json.load(f)
        if isinstance(result, list) and isinstance(data, list):
            result.extend(data)
        elif isinstance(result, dict) and isinstance(data, dict):
            result.update(data)
        save_data_to_json(data=result, file_name=file_name, key='w')

    if DEBUG and SAVING:
        logger.debug(f"{path} saved.")


@logger.catch
def save_data_to_txt(data: Union[dict, list], file_name: str = "data.json"):
    with open(file_name, 'w', encoding='utf-8') as f:
        data = "\n".join(data)
        f.write(data)

    if DEBUG and SAVING:
        logger.debug(f"{file_name} saved.")


@logger.catch
def check_is_int(text: str) -> int:
    """Проверяет что в строке пришло положительное число и возвращает его обратно если да"""

    if text.isdigit():
        if int(text) > 0:
            return int(text)

    return 0


@logger.catch
def load_statistics(filename: str = 'errors.txt') -> list[str]:
    filepath = os.path.join('logs', 'saved_files', filename)
    result = []
    if not os.path.exists(filepath):
        filepath = '..' + os.sep + filepath
        if not os.path.exists(filepath):
            logger.error(f"File {filepath} not found.")
            return result
    with open(filepath, 'r', encoding='utf-8') as f:
        result: list[str] = f.readlines()

    return result


@logger.catch
def get_current_time() -> datetime:
    """Возвращает текущее время целое."""

    return datetime.datetime.utcnow().replace(tzinfo=None)


@logger.catch
def get_current_timestamp() -> int:
    """Возвращает текущее время (timestamp) целое."""

    return int(get_current_time().timestamp())

@logger.catch
def get_from_timestamp(data: float) -> datetime:
    """Возвращает текущее время из timstamp."""

    return datetime.datetime.fromtimestamp(data)

