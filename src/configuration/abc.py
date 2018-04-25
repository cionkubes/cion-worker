from abc import ABCMeta, abstractmethod


class ConfigABC(metaclass=ABCMeta):
    @abstractmethod
    def set(self, update):
        pass

    @abstractmethod
    def delete(self, old):
        pass