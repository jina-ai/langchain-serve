from functools import wraps
import inspect
from typing import Callable


def serving(_func=None, *, websocket: bool = False, auth: Callable = None):
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        if inspect.iscoroutinefunction(func):
            wrapper = async_wrapper
        else:
            wrapper = sync_wrapper

        _args = {
            'name': func.__name__,
            'doc': func.__doc__,
            'params': {
                'include_callback_handlers': websocket,
                # If websocket is True, pass the callback handlers to the client.
                'auth': auth,
            },
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
