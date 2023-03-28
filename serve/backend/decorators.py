from functools import wraps
from typing import Callable


def serving(func: Callable):
    __serve__ = {'name': func.__name__, 'doc': func.__doc__, 'params': {}}

    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    wrapper.__serve__ = __serve__
    return wrapper
