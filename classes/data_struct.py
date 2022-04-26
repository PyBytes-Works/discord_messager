class Menu:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, str(key), str(value))
