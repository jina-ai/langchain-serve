import asyncio

from lcserve import serving


@serving
async def async_http(interval: int) -> str:
    await asyncio.sleep(interval)
    return 'Hello, world!'
