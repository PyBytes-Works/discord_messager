import os

import pytest
from dotenv import load_dotenv
try:
    load_dotenv()
except:
    pass


pytest_plugins = [
    'tests.datastore.datastore_fixtures',
]


PROXY_USER: str = os.getenv('PROXY_USER')
PROXY_PASSWORD: str = os.getenv('PROXY_PASSWORD')
DEFAULT_PROXY: str = os.getenv('DEFAULT_PROXY')
BASE_API_URL: str = os.getenv('BASE_API_URL')
PROXY_TEST_URL: str = os.getenv('PROXY_TEST_URL')
ADMINS: list = os.getenv('ADMINS')[1:-1].replace('"', '').split(',')
PROXIES: list[str] = os.getenv('PROXIES')[1:-1].replace('"', '').split(',')
TEST_DISCORD_TOKEN: str = os.getenv('TEST_DISCORD_TOKEN')
CHANNEL: int = int(os.getenv('CHANNEL'))
ANTICAPTCHA_KEY: str = os.getenv('ANTICAPTCHA_KEY')


@pytest.fixture
def proxies() -> list[str]:
    return PROXIES


@pytest.fixture
def token() -> str:
    return TEST_DISCORD_TOKEN


@pytest.fixture
def proxy() -> str:
    return DEFAULT_PROXY


@pytest.fixture
def admin() -> str:
    return ADMINS[0]


@pytest.fixture
def channel() -> int:
    return CHANNEL


@pytest.fixture
def anticaptcha_key() -> str:
    return ANTICAPTCHA_KEY
