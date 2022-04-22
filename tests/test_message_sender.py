import asyncio

from classes.message_sender import MessageSender
from fake_data import *


async def tests():
    print(await MessageSender(datastore=datastore).send_message(text=''))


if __name__ == '__main__':
    try:
        asyncio.new_event_loop().run_until_complete(tests())
    except KeyboardInterrupt:
        pass
