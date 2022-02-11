import asyncio
import datetime
import json
import os.path
import re
from typing import List

import requests
import random
from bs4 import BeautifulSoup as bs

from models import Token


def get_free_proxies() -> list:
    url = "https://free-proxy-list.net/"
    soup = bs(requests.get(url).content, "html.parser")
    text = soup.text
    proxies = re.findall(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,6}\b', text)

    return proxies


def get_random_token(file_name: str = "dis_tokens.json"):
    if os.path.exists(file_name):
        with open(file_name, 'r', encoding='utf-8') as f:
            data = json.load(f)

    return random.choice(data)


def select_token_for_work(telegram_id: str):
    """
    Выбирает случайного токена дискорда из свободных, если нет свободных - пишет сообщение что
    свободных нет.
    """

    cooldown = 300
    all_user_tokens: List[dict] = Token.get_all_user_tokens(telegram_id=telegram_id)
    current_time = int(datetime.datetime.now().timestamp())
    tokens_for_job: list = [
        key
        for elem in all_user_tokens
        for key, value in elem.items()
        if current_time > value["time"] + value["cooldown"]
    ]
    print(len(tokens_for_job))
    if tokens_for_job:
        random_token = random.choice(tokens_for_job)

        # save token to class data
    else:
        closest_token_time = abs(min(value["time"] for elem in all_user_tokens for value in elem.values()) - current_time)
        delay = cooldown - closest_token_time
        if delay > 60:
            delay = f"{delay // 60}:{delay % 60}"
            text = "minutes"
        else:
            text = "seconds"
        print(f"All tokens busy. Please wait {delay} {text}.")


def do_job(random_token):
    # After sending message do this
    Token.update_token_time(random_token)


if __name__ == '__main__':
    # current_user = "test1"
    # try:
    #
    #     select_token_for_work(current_user)
    # except KeyboardInterrupt:
    #     print("END")
    pass

