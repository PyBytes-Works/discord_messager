import asyncio

from classes.request_sender import *
from fake_data import *


async def tests():
    print(await GetMe().get_discord_id(token=token, proxy=DEFAULT_PROXY))
    print(await ProxyChecker().check_proxy(DEFAULT_PROXY))
    print(await TokenChecker().check_token(token=token, proxy=DEFAULT_PROXY, channel=channel))
    print(await SendMessageToChannel(datastore=datastore).send_data())


if __name__ == '__main__':
    try:
        asyncio.new_event_loop().run_until_complete(tests())
    except KeyboardInterrupt:
        pass
