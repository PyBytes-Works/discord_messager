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
    mes = [
        {
            "id": "965957344892686376",
            "timestamp": "2022-04-19T12:49:37.642000+00:00"
        },
        {
            "id": "965957052100919316",
            "timestamp": "2022-04-19T12:48:27.835000+00:00"
        }
    ]
    mmm = max(mes, key=lambda x: x.get("timestamp"))
    print(mmm)
