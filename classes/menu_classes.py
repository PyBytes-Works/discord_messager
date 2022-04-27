class Menu:
    def __init__(self, **kwargs):
        self.delete = None
        self.cooldown = None
        self.rename = None
        for key, value in kwargs.items():
            setattr(self, str(key), str(value))
