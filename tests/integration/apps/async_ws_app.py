import asyncio
import time

from lcserve import serving


@serving(websocket=True)
async def async_ws(interval: int, **kwargs) -> str:
    ws: 'WebSocket' = kwargs['websocket']
    for i in range(1000):
        await ws.send_text(str(i))
        await asyncio.sleep(interval)

    return 'hello world'
