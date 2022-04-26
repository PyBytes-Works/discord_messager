class Menu:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            getattr(self, str(key), str(value))
