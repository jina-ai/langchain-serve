import json

import pytest
import websockets

from .test_helper import run_test_server


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "run_test_server, route",
    [("sync_ws_app", "sync_ws"), ("async_ws_app", "async_ws")],
    indirect=["run_test_server"],
)
async def test_app(run_test_server, route):
    async with websockets.connect(f"ws://localhost:8080/{route}") as websocket:
        await websocket.send(json.dumps({"interval": 1}))

        received_messages = []
        for _ in range(5):
            message = await websocket.recv()
            received_messages.append(message)

        assert received_messages == ["0", "1", "2", "3", "4"]
