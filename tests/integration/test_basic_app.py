import json

import pytest
import requests
import websockets

from .test_helper import run_test_server


@pytest.mark.parametrize(
    "run_test_server, route",
    [("basic_app", "sync_http"), ("basic_app", "async_http")],
    indirect=["run_test_server"],
)
def test_basic_app_http(run_test_server, route):
    url = "http://localhost:8080/" + route
    headers = {
        "accept": "application/json",
        "Content-Type": "application/json",
    }
    data = {"interval": 3, "envs": {}}
    response = requests.post(url, headers=headers, json=data)
    response_data = response.json()

    assert response.status_code == 200
    assert response_data["result"] == "Hello, world!"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "run_test_server, route",
    [("basic_app", "sync_ws"), ("basic_app", "async_ws")],
    indirect=["run_test_server"],
)
async def test_basic_app_ws(run_test_server, route):
    async with websockets.connect(f"ws://localhost:8080/{route}") as websocket:
        await websocket.send(json.dumps({"interval": 1}))

        received_messages = []
        for _ in range(5):
            message = await websocket.recv()
            received_messages.append(message)

        assert received_messages == ["0", "1", "2", "3", "4"]
