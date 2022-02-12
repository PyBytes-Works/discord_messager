import asyncio
import datetime
import json
import os.path
import re
from typing import List

import aiohttp
import requests
import random
from bs4 import BeautifulSoup as bs

import discord_handler
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

async def check_token(token: str, proxy: str, channel: int) -> str:
    """Returns valid token else 'bad token'"""

    async with aiohttp.ClientSession() as session:
        session.headers['authorization']: str = token
        limit: int = 1
        # url: str = f'https://discord.com/api/v9/channels/' + f'{channel}/messages?limit={limit}'
        result: str = 'bad token'
        user = 'Selkaifusa2000'
        password = 'V9f3WuD'
        url = 'http://www.google.com'
        try:
            proxy = f"http://{user}:{password}@{proxy}/"
            async with session.get(url=url, proxy=proxy, ssl=False) as response:
                print(response.url)
            # async with session.get(url=url, timeout=10) as response:
                if response.status == 200:
                    print(response.status)
                    result = token
        except (asyncio.exceptions.TimeoutError,
        aiohttp.client_exceptions.ServerDisconnectedError,
        aiohttp.client_exceptions.ClientProxyConnectionError,
        aiohttp.client_exceptions.ClientHttpProxyError,
        aiohttp.client_exceptions.ClientOSError,
        aiohttp.client_exceptions.TooManyRedirects,
        ConnectionResetError) as err:
            print(f"Token check Error: {err}")

    return result


async def text():
    async with aiohttp.ClientSession() as session:
        session.headers['authorization']: str = token



if __name__ == '__main__':
    PROXY_USER = discord_handler.PROXY_USER
    # PROXY_PASSWORD = discord_handler.PROXY_PASSWORD
    token = 'NDg3OTYyMDczNDU2ODM2NjE4.YfbEhA.gXDarmEjAxjw_d2R92oc-02xejA'
    proxy = "191.101.121.195:45785"
    user = 'Selkaifusa2000'
    password = 'V9f3WuD'
    channel = 932256559394861079
    # asyncio.new_event_loop().run_until_complete(
    #     check_token(token=token, proxy=proxy, channel=932256559394861079))
    # url = 'http://ifconfig.me/ip'
    url = 'http://www.google.com'


    proxies = {
        "http": f"http://{user}:{password}@{proxy}/"
    }
    limit = 1
    # url: str = f'https://discord.com/api/v9/channels/' + f'{channel}/messages?limit={limit}'
    useragentz = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.61 Safari/537.36'
    headers = {
        # "authorization": "NDg3OTYyMDczNDU2ODM2NjE4.YfbEhA.gXDarmEjAxjw_d2R92oc-02xejA",
        'User-agent': useragentz
    }
    response = requests.get(url=url, proxies=proxies, headers=headers)
    print(response.status_code)
    # print(response.status_code)

    # current_user = "test1"
    # try:
    #
    #     select_token_for_work(current_user)
    # except KeyboardInterrupt:
    #     print("END")
    pass

