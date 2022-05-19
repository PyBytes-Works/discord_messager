import pytest

from classes.token_datastorage import TokenData
from fake_data import *


@pytest.fixture
def datastore():
    datastore = TokenData(telegram_id=telegram_id)
    datastore.token = token
    datastore.proxy = proxy
    datastore.channel = str(channel)
    datastore.text_to_send = text
    datastore.data_for_send.update(content=text)
    return datastore
