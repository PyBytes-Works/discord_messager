import asyncio

from classes.message_sender import MessageSender
from config import SEMAPHORE
from fake_data import datastore


async def test_get_request_semaphore():
    sender = MessageSender(datastore=datastore)
    tasks_count = 101
    tasks = []
    for _ in range(tasks_count):
        tasks.append(asyncio.create_task(sender.send_message_to_discord()))
    responses = await asyncio.gather(*tasks)
    assert len(responses) == tasks_count
