from classes.token_datastorage import TokenData
from conftest import *


@pytest.fixture
def datastore():
    datastore = TokenData(telegram_id=ADMINS[0])
    datastore.token = TEST_DISCORD_TOKEN
    datastore.proxy = DEFAULT_PROXY
    datastore.channel = str(CHANNEL)
    datastore.text_to_send = 'test text'
    datastore.data_for_send.update(content='content text')
    return datastore
