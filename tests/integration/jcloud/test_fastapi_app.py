import json

import aiohttp
import pytest
import requests

from ..helper import deploy_jcloud_fastapi_app


@pytest.mark.asyncio
async def test_basic_app():
    async with deploy_jcloud_fastapi_app() as app_id:
        _test_http_route(app_id)
        await _test_ws_route(app_id)


def _test_http_route(app_id):
    headers = {
        "accept": "application/json",
        "Content-Type": "application/json",
    }
    response = requests.get(f"https://{app_id}.wolf.jina.ai/status", headers=headers)

    response_data = response.json()

    assert response.status_code == 200
    assert response_data == {"Hello": "World"}


async def _test_ws_route(app_id):
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(f"wss://{app_id}.wolf.jina.ai/ws") as websocket:
            await websocket.send_json({"interval": 1})
            received_messages = []
            async for message in websocket:
                received_messages.append(message.data)
            assert received_messages[1:] == ["0", "1", "2", "3", "4"]
