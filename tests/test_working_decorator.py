from classes.discord_manager import DiscordManager, asyncio


async def tests():
    man = DiscordManager(message=message, mute=False)
    # man.working = True
    # print("Test DiscordManager: ", await man.lets_play())
    print(dir(man))


if __name__ == '__main__':

    class User:

        username = "deskent"
        id = "555"

    class Message:

        from_user = User()


    message = Message()
    try:
        asyncio.new_event_loop().run_until_complete(tests())
    except KeyboardInterrupt:
        pass
