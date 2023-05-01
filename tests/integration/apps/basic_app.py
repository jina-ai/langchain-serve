import asyncio
import time
from typing import List, Dict
from lcserve import serving

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


def authorizer(token: str) -> bool:
    print(f"Got token: {token}")
    return token == "mysecrettoken"


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
