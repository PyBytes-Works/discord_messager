import asyncio

from classes.message_receiver import MessageReceiver
from fake_data import *


async def tests():
    print(await MessageReceiver(datastore=datastore).get_message())


if __name__ == '__main__':
    try:
        asyncio.new_event_loop().run_until_complete(tests())
    except KeyboardInterrupt:
        pass
