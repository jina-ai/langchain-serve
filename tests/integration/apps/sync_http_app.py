import time

from lcserve import serving


@serving
def sync_http(interval: int) -> str:
    time.sleep(interval)
    return 'Hello, world!'
