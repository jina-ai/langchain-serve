import asyncio
import time

from lcserve import serving


@serving(websocket=True)
def sync_ws(interval: int, **kwargs) -> str:
    ws: 'WebSocket' = kwargs['websocket']
    for i in range(1000):
        asyncio.run(ws.send_text(str(i)))
        time.sleep(interval)

    return 'hello world'
