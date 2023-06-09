import asyncio
import time
from typing import List, Dict, Any
from lcserve import serving

import aiofiles
from fastapi import WebSocket, UploadFile


@serving
def sync_http(interval: int) -> str:
    time.sleep(interval)
    return "Hello, world!"


@serving
async def async_http(interval: int) -> str:
    await asyncio.sleep(interval)
    return "Hello, world!"


@serving(websocket=True)
def sync_ws(interval: int, **kwargs) -> str:
    ws: "WebSocket" = kwargs["websocket"]
    for i in range(1000):
        asyncio.run(ws.send_text(str(i)))
        time.sleep(interval)

    return "hello world"


@serving(websocket=True)
async def async_ws(interval: int, **kwargs) -> str:
    ws: "WebSocket" = kwargs["websocket"]
    for i in range(1000):
        await ws.send_text(str(i))
        await asyncio.sleep(interval)

    return "hello world"


def authorizer(token: str) -> str:
    print(f"Got token: {token}")
    if not token == "mysecrettoken":
        raise Exception("Invalid token")

    return "username"


@serving(auth=authorizer)
def sync_auth_http(interval: int) -> str:
    time.sleep(interval)
    return "Hello, world!"


@serving(websocket=True, auth=authorizer)
async def sync_auth_ws(interval: int, **kwargs) -> str:
    ws: "WebSocket" = kwargs["websocket"]
    for i in range(1000):
        await ws.send_text(str(i))
        await asyncio.sleep(interval)

    return "hello world"


@serving(auth=authorizer)
def sync_auth_http_auth_response(interval: int, **kwargs) -> str:
    assert 'auth_response' in kwargs
    assert kwargs['auth_response'] == "username"
    time.sleep(interval)
    return "Hello, world!"


@serving(websocket=True, auth=authorizer)
async def sync_auth_ws_auth_response(interval: int, **kwargs) -> str:
    assert 'auth_response' in kwargs
    assert kwargs['auth_response'] == "username"
    ws: "WebSocket" = kwargs["websocket"]
    for i in range(1000):
        await ws.send_text(str(i))
        await asyncio.sleep(interval)

    return "hello world"


@serving
def single_file_upload(file: UploadFile) -> str:
    return file.filename


@serving
def single_file_upload_with_extra_arg(
    file: UploadFile, question: str, someint: int
) -> Dict[str, str]:
    return {
        "file": file.filename,
        "question": question,
        "someint": someint,
    }


@serving
def multiple_file_uploads(f1: UploadFile, f2: UploadFile) -> List[str]:
    return [f1.filename, f2.filename]


@serving
def multiple_file_uploads_with_extra_arg(
    f1: UploadFile, f2: UploadFile, question: str, someint: int
) -> Dict[str, str]:
    return {
        "f1": f1.filename,
        "f2": f2.filename,
        "question": question,
        "someint": someint,
    }


@serving
def store(text: str, **kwargs):
    workspace: str = kwargs.get('workspace')
    path = f'{workspace}/store.txt'
    print(f'Writing to {path}')
    with open(path, 'a') as f:
        f.writelines(text + '\n')
    return 'OK'


@serving(websocket=True)
async def stream(**kwargs):
    workspace: str = kwargs.get('workspace')
    websocket: WebSocket = kwargs.get('websocket')
    path = f'{workspace}/store.txt'
    print(f'Streaming {path}')
    async with aiofiles.open(path, 'r') as f:
        async for line in f:
            await websocket.send_text(line)
    return 'OK'


@serving
def readfile() -> str:
    with open('a.txt', 'r') as f:  # a.txt is in the root of the project
        return f.read()


@serving(websocket=True)
def readfile_ws(**kwargs) -> str:
    with open('a.txt', 'r') as f:  # a.txt is in the root of the project
        return f.read()
