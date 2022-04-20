from classes.request_sender import RequestSender
from config import logger
from classes.db_interface import DBI


class ProxyChecker:
    def __init__(self):
        self.proxy: str = ''

    @logger.catch
    async def get_proxy(self, telegram_id: str) -> str:
        """Возвращает рабочую прокси из базы данных, если нет рабочих возвращает 'no proxies'"""

        if not await DBI.get_proxy_count():
            return 'no proxies'
        self.proxy: str = str(await DBI.get_proxy(telegram_id=telegram_id))
        if await self._is_proxy_work(proxy=self.proxy):
            return self.proxy
        if not await DBI.update_proxies_for_owners(proxy=self.proxy):
            return 'no proxies'

        return await self.get_proxy(telegram_id=telegram_id)

    @logger.catch
    async def _is_proxy_work(self) -> bool:
        """Проверяет прокси на работоспособность"""

        if await RequestSender().check_proxy(proxy=self.proxy) == 200:
            return True
