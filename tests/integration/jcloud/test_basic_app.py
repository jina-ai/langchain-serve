import json

import pytest
import requests
import websockets

from ..helper import deploy_jcloud_app


@pytest.mark.asyncio
async def test_basic_app():
    async with deploy_jcloud_app() as app_id:
        _test_http_route(app_id)
        await _test_ws_route(app_id)


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
        for _ in range(5):
            message = await websocket.recv()
            received_messages.append(message)

        assert received_messages == ["0", "1", "2", "3", "4"]
