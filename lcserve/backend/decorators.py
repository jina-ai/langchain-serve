from functools import wraps


def serving(_func=None, *, websocket: bool = False):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        _args = {
            'name': func.__name__,
            'doc': func.__doc__,
            'params': {},
        }
        if websocket:
            wrapper.__ws_serving__ = _args
        else:
            wrapper.__serving__ = _args

        return wrapper

    if _func is None:
        return decorator
    else:
        return decorator(_func)
