import asyncio
import json
import math
import time

import pytest
import requests
import websockets

from ..helper import deploy_jcloud_app


@pytest.mark.asyncio
async def test_http_route_timeout():
    timeout = 60
    async with deploy_jcloud_app(timeout=timeout) as app_id:
        _test_http_route(app_id, timeout)
        await _test_ws_route(app_id, timeout)


def _test_http_route(app_id, timeout):
    headers = {
        "accept": "application/json",
        "Content-Type": "application/json",
    }
    data = {"interval": 10000, "envs": {}}

    start_time = time.time()
    response = requests.post(
        f"https://{app_id}.wolf.jina.ai/sync_http", headers=headers, json=data
    )

    if response.status_code == 504:
        assert math.isclose(
            time.time() - start_time, timeout, abs_tol=5
        ), "HTTP request timed out at an unexpected time"
    else:
        pytest.fail(
            f"The request should have returned a 504 Gateway Timeout status code, time taken: {time.time() - start_time}, status code: {response.status_code}"
        )


async def _test_ws_route(app_id, timeout):
    async with websockets.connect(f"wss://{app_id}.wolf.jina.ai/sync_ws") as websocket:

        async def _receive_messages(websocket):
            messages = []
            try:
                async for message in websocket:
                    messages.append(json.loads(message))
            except websockets.ConnectionClosed:
                pass
            return messages

        start_time = time.time()
        try:
            await websocket.send(json.dumps({"interval": 1}))
            receive_task = asyncio.create_task(_receive_messages(websocket))
            await asyncio.wait_for(receive_task, timeout=timeout)
        except asyncio.TimeoutError:
            assert math.isclose(
                time.time() - start_time, timeout, abs_tol=5
            ), "WebSocket request timed out at an unexpected time"
        except websockets.exceptions.ConnectionClosed as e:
            pytest.fail(f"The WebSocket connection was closed unexpectedly: {e}")
        else:
            pytest.fail("The WebSocket connection should have timed out")
