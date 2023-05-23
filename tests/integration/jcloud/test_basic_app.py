import json

import pytest
import requests
import websockets
from websockets.exceptions import ConnectionClosedOK

from ..helper import deploy_jcloud_app


@pytest.mark.asyncio
async def test_basic_app():
    async with deploy_jcloud_app() as app_id:
        _test_http_route(app_id)
        await _test_ws_route(app_id)
        await _test_workspace(app_id)


def _test_http_route(app_id):
    headers = {
        "accept": "application/json",
        "Content-Type": "application/json",
    }
    data = {"interval": 1, "envs": {}}

    response = requests.post(
        f"https://{app_id}.wolf.jina.ai/sync_http", headers=headers, json=data
    )

    response_data = response.json()

    assert response.status_code == 200
    assert response_data["result"] == "Hello, world!"


async def _test_ws_route(app_id):
    async with websockets.connect(f"wss://{app_id}.wolf.jina.ai/sync_ws") as websocket:
        await websocket.send(json.dumps({"interval": 1}))

        received_messages = []
        for _ in range(6):
            message = await websocket.recv()
            received_messages.append(message)

        assert received_messages[1:] == ["0", "1", "2", "3", "4"]


async def _test_workspace(app_id):
    http_url = f"https://{app_id}.wolf.jina.ai/store"
    ws_url = f"wss://{app_id}.wolf.jina.ai/stream"

    for i in range(10):
        data = {"text": f"Here's string {i}", "envs": {}}
        response = requests.post(http_url, json=data)
        assert response.status_code == 200

    try:
        async with websockets.connect(ws_url) as websocket:
            await websocket.send(json.dumps({}))

            received_messages = []
            for _ in range(10):
                message = await websocket.recv()
                received_messages.append(message.strip())

            assert received_messages[1:] == [f"Here's string {i}" for i in range(10)]
    except ConnectionClosedOK:
        pass
