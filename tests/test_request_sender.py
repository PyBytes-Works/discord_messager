from classes.message_sender import MessageSender
from classes.request_classes import *
from fake_data import *


async def tests():
    # print("Discord id:", await GetMe().get_discord_id(token=token, proxy=proxy))
    # print("Discord id:", await GetMe().get_discord_id(token=token, proxy=bad_proxy))
    print("Proxy:", await ProxyChecker().get_checked_proxy(telegram_id=telegram_id))
    # print(await TokenChecker().check_token(token=token, proxy=proxy, channel=channel, telegram_id=telegram_id))
    # print(await MessageSender(datastore).send_message())


if __name__ == '__main__':
    try:
        asyncio.new_event_loop().run_until_complete(tests())
    except KeyboardInterrupt:
        pass


    """
    bad channel:
    '{"code": 50035, "errors": {"channel_id": {"_errors": [{"code": "NUMBER_TYPE_MAX", "message": "snowflake value should be less than or equal to 9223372036854775807."}]}}, "message": "Invalid Form Body"}'

    empty:
    {'status': 400, 'data': '{"message": "Cannot send an empty message", "code": 50006}'}

    """
