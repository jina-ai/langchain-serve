import asyncio
import time
from typing import Union

from fastapi import FastAPI, WebSocket

app = FastAPI()


@app.get("/status")
def read_root():
    time.sleep(1)
    return {"Hello": "World"}


@app.get("/astatus")
async def get_astatus():
    await asyncio.sleep(1)
    return {"Hello": "World"}


@app.get("/sleep")
async def sleep(interval: int):
    await asyncio.sleep(interval)
    return {"Hello": "World"}


@app.get("/items/{item_id}")
def get_item(item_id: int, q: Union[str, None] = None):
    time.sleep(1)
    return {"item_id": item_id, "q": q}


@app.get("/aitems/{item_id}")
async def get_aitem(item_id: int, q: Union[str, None] = None):
    await asyncio.sleep(1)
    return {"item_id": item_id, "q": q}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, interval: int = 1):
    await websocket.accept()
    try:
        for i in range(5):
            await websocket.send_text(str(i))
            await asyncio.sleep(interval)
        await websocket.close()
    except Exception as e:
        print(e)
