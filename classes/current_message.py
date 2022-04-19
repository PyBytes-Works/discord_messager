class CurrentMessage:

    def __init__(self, id: str, message: str, channel_id: str, timestamp: str, author: dict):
        self.id: str = id
        self.message: str = message
        self.channel_id: str = channel_id
        self.author: dict = author
        self.timestamp: str = timestamp

    def get_dict(self) -> dict:
        return self.__dict__

    def __str__(self):
        return f"{self.__dict__}"


if __name__ == '__main__':
    a = CurrentMessage("123", "hello", "555", '0005', {"name": "vasya", 'values':{'total': 5}})
    print(a)
    data: dict = a.get_dict()
    print(data)
    total = data.get("author").get("values").get("total")
    print(total)
