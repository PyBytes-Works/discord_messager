import asyncio

from classes.message_sender import MessageSender
from fake_data import proxies


async def test_send_messages(datastore):
    tasks_count = len(proxies)
    tasks = []
    for proxy in proxies:
        text: str = f'Test message from proxy: {proxy}'
        datastore.proxy = proxy
        datastore.text_to_send = text
        datastore.data_for_send.update(content=text)
        sender = MessageSender(datastore=datastore)
        tasks.append(asyncio.create_task(sender.send_message_to_discord()))
    responses = await asyncio.gather(*tasks)
    assert len(responses) == tasks_count
