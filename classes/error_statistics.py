import json

from config import logger
from utils import load_statistics


class Statistic:

    @classmethod
    @logger.catch
    def get_errors(cls):
        data: list[str] = load_statistics()
        errors: list[dict] = [json.loads(elem) for elem in data]
        print(errors)


if __name__ == '__main__':
    a = Statistic()
    a.get_errors()
