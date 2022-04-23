from classes.request_sender import *
from fake_data import *


async def tests():
    print(await GetMe().get_discord_id(token=token, proxy=proxy))
    print(await ProxyChecker().get_checked_proxy(telegram_id=telegram_id))
    print(await TokenChecker().check_token(token=token, proxy=proxy, channel=channel))
    print(await SendMessageToChannel(datastore=datastore).send_data())


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
