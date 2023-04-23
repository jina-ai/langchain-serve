import asyncio
import time

from lcserve import serving


@serving
def sync_http(interval: int) -> str:
    time.sleep(interval)
    return 'Hello, world!'


@serving
async def async_http(interval: int) -> str:
    await asyncio.sleep(interval)
    return 'Hello, world!'


@serving(websocket=True)
def sync_ws(interval: int, **kwargs) -> str:
    ws: 'WebSocket' = kwargs['websocket']
    for i in range(1000):
        asyncio.run(ws.send_text(str(i)))
        time.sleep(interval)

    return 'hello world'


@serving(websocket=True)
async def async_ws(interval: int, **kwargs) -> str:
    ws: 'WebSocket' = kwargs['websocket']
    for i in range(1000):
        await ws.send_text(str(i))
        await asyncio.sleep(interval)

    return 'hello world'
