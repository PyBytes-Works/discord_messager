import pytest
from classes.token_datastorage import TokenData


@pytest.fixture
def datastore(admin, token, proxy, channel):
    datastore = TokenData(telegram_id=admin)
    datastore.token = token
    datastore.proxy = proxy
    datastore.channel = str(channel)
    datastore.text_to_send = 'test text'
    datastore.data_for_send.update(content='content text')
    return datastore
