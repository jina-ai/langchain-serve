from functools import wraps
from typing import Callable


def serving(func: Callable):
    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    wrapper.__serving__ = {
        'name': func.__name__,
        'doc': func.__doc__,
        'params': {},
    }
    return wrapper
