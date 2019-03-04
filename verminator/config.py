__all__ = ['verminator_config']
import os


class SingletonMetaClass(type):
    """ A metaclass that creates a Singleton base class when called. """
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(SingletonMetaClass, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class Singleton(SingletonMetaClass('SingletonMeta', (object,), {})):
    pass


class VerminatorConfig(Singleton):
    _OEM_ORIGIN = 'tdc'
    OEM_NAME = 'tdc'

    def set_oem(self, oemname):
        if oemname is not None:
            self.OEM_NAME = oemname
        elif os.getenv('OEM_NAME', ''):
            self.OEM_NAME = os.getenv('OEM_NAME')


verminator_config = VerminatorConfig()
