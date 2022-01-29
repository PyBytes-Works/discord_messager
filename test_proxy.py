import json
import os.path
import re

import requests
import random
from bs4 import BeautifulSoup as bs

from utils import save_data_to_json


def get_free_proxies() -> list:
    url = "https://free-proxy-list.net/"
    # посылаем HTTP запрос и создаем soup объект
    soup = bs(requests.get(url).content, "html.parser")
    text = soup.text
    proxies = re.findall(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,6}\b', text)
    # proxies = []


    # if soup:
    #     for row in soup.find("table", attrs={"id": "proxylisttable"}).find_all("tr")[1:]:
    #         tds = row.find_all("td")
    #         try:
    #             ip = tds[0].text.strip()
    #             port = tds[1].text.strip()
    #             host = f"{ip}:{port}"
    #             proxies.append(host)
    #         except IndexError:
    #             continue
    #
    return proxies


def get_session(proxies):
    # создаем сессию для отправки HTTP запроса
    session = requests.Session()
    # выбираем случайным образом один из адресов
    proxy = random.choice(proxies)
    session.proxies = {"http": proxy, "https": proxy}

    return session


def check_session():
    proxies: list = get_proxies()
    good_proxies = []
    for i in range(len(proxies)):
        s = get_session(proxies)
        try:
            proxy = s.get("http://icanhazip.com", timeout=1.5).text.strip()
            print("Request page with IP:", proxy)
            good_proxies.append(i)
        except Exception as e:
            continue

    return good_proxies

# def check_proxy():
#     # url = 'http://ifconfig.me/all.json'
#     url = "http://icanhazip.com"
#     proxies = {'http': '207.154.231.208:3128'}
#
#     response = requests.get(url=url, proxies=proxies)
#     # response.close()#
#     print(response.status_code)

def req():
    # url = "https://www.google-analytics.com/j/collect?v=1&_v=j96&a=659062610&t=pageview&_s=1&dl=https%3A%2F%2Ffree-proxy-list.net%2F&ul=ru-ru&de=UTF-8&dt=Free%20Proxy%20List%20-%20Just%20Checked%20Proxy%20List&sd=24-bit&sr=1920x1080&vp=535x937&je=0&_u=AACAAEABAAAAAC~&jid=196714686&gjid=237017926&cid=608108730.1643363610&tid=UA-158616-8&_gid=552263806.1643363610&_r=1&_slc=1&z=282637364"
    url = "https://free-proxy-list.net/"
    resp = requests.get(url=url)
    status = resp.status_code
    if status == 200:
        try:
            data = resp.json()
        except Exception as err:
            print(resp.text)
            print(err)
        else:
            save_data_to_json(data, "req.json")
    else:

        print(resp.status_code)


def load_proxies(file_name: str = "proxies.json") -> list:
    data = []
    if os.path.exists(file_name):
        with open(file_name) as f:
            data = json.load(f)

    return data


def get_random_token(file_name: str = "dis_tokens.json"):
    if os.path.exists(file_name):
        with open(file_name, 'r', encoding='utf-8') as f:
            data = json.load(f)

    return random.choice(data)



if __name__ == '__main__':
    pass
    # pr = get_free_proxies()
    # save_data_to_json(check_session(), file_name="good_proxies.json")

    # proxies = load_proxies()
