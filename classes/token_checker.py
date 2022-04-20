from classes.request_sender import RequestSender
from config import logger
from classes.db_interface import DBI


class TokenChecker:

    def __init__(self, proxy: str, token: str = '', channel: int = 0):
        self.proxy: str = proxy
        self.token: str = token
        self.channel: int = channel

    @logger.catch
    async def check_user_data(self) -> dict:
        """Returns checked dictionary for user data
        Save valid data to instance variables """

        answer: dict = {
            "success": False,
            "message": '',
            "data": {}
        }

        request_result: str = await self.__check_token()
        result = {"token": request_result}
        if request_result != "bad token":
            result["channel"] = self.channel
        elif request_result == 'no proxies':
            return {"token": request_result}

        return answer

    @logger.catch
    async def __check_token(self) -> str:
        """Returns valid token else 'bad token'"""

        # TODO дописать для всех случаев
        result: str = 'bad token'
        rs = RequestSender()
        status: int = await rs.check_proxy(proxy=self.proxy, token=self.token, channel=self.channel)
        if status == 200:
            result = self.token
        elif status == 407:
            if not await DBI.update_proxies_for_owners(self.proxy):
                return 'no proxies'

        return result
