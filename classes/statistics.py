import json

from config import logger
from utils import load_statistics, save_data_to_json


class Statistic:

    @classmethod
    @logger.catch
    def get_errors(cls):
        data: list[str] = load_statistics()
        json_data: list[dict] = [json.loads(elem) for elem in data]
        errors: list[dict] = [elem for elem in json_data if elem.get("record", {}).get("level", {}).get("name") == "ERROR"]
        save_data_to_json(data=errors, file_name='error_statistics.json')
        # for error in errors:
        #     print(error)


if __name__ == '__main__':
    a = Statistic()
    a.get_errors()
