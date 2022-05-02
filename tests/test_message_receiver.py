import asyncio

from classes.message_manager import MessageManager
from fake_data import *


async def tests():
    print(await MessageManager(datastore=datastore).handling_messages())


if __name__ == '__main__':
    try:
        asyncio.new_event_loop().run_until_complete(tests())
    except KeyboardInterrupt:
        pass
