from classes.message_sender import MessageSender
from classes.request_classes import *
from fake_data import *


async def test_all_proxies():
    counter = 0
    for proxy in proxies:
        result = await GetMe().get_discord_id(token=token, proxy=proxy)
        print(f"\nChecking proxy: {proxy}"
              f"\n\tResult: {result}")
        if result:
            counter += 1
    print(f"Total proxies: {len(proxies)}")
    print(f"Working: {counter}")


async def tests():
    # print("Discord id:", await GetMe().get_discord_id(token=token, proxy=proxy))
    # print("Discord id:", await GetMe().get_discord_id(token=token, proxy=bad_proxy))
    # print("Proxy:", await ProxyChecker().get_checked_proxy(telegram_id=telegram_id))
    print(await TokenChecker().check_token(token="ksdf", proxy=proxy, channel=channel, telegram_id=telegram_id))
    # print(await MessageSender(datastore).send_message())
    # await test_all_proxies()

if __name__ == '__main__':

    proxies = (
        "213.226.71.112:45785",
        "51.38.116.213:45785",
        "185.242.85.250:45785",
        "80.82.222.140:45785",
        "46.228.205.187:45785",
        "62.113.216.167:45785",
        "54.38.154.153:45785",
        "185.17.123.31:45785",
        "51.68.178.15:45785",
        "195.54.32.129:45785",
    )

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
