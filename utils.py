import json

from typing import Union


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
