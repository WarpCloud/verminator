__all__ = ['VerminatorConfig']
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
    OEM_NAME = os.getenv('OEM_NAME') if os.getenv('OEM_NAME', '') else 'tdc'
