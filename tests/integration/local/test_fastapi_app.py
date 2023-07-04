import json
import os
import time

import aiohttp
import pytest
import requests
import websockets

from ..helper import (
    examine_request_count_with_retry,
    examine_request_duration_with_retry,
    run_fastapi_app_locally,
)

HOST = "localhost:8080"
HTTP_HOST = f"http://{HOST}"
WS_HOST = f"ws://{HOST}"
APP = "tests.integration.fastapi_app.endpoints:app"


@pytest.mark.parametrize(
    "run_fastapi_app_locally, route",
    [(APP, "startup_check")],
    indirect=["run_fastapi_app_locally"],
)
def test_start_up_event_with_gateway(run_fastapi_app_locally, route):
    url = os.path.join(HTTP_HOST, route)
    headers = {
        "accept": "application/json",
        "Content-Type": "application/json",
    }
    response = requests.get(url, headers=headers)
    response_data = response.json()

    assert response.status_code == 200
    assert response_data == {"startup_event_ran": True}


@pytest.mark.parametrize(
    "run_fastapi_app_locally, route",
    [(APP, "status"), (APP, "astatus")],
    indirect=["run_fastapi_app_locally"],
)
def test_get_status_endpoints(run_fastapi_app_locally, route):
    url = os.path.join(HTTP_HOST, route)
    headers = {
        "accept": "application/json",
        "Content-Type": "application/json",
    }
    response = requests.get(url, headers=headers)
    response_data = response.json()

    assert response.status_code == 200
    assert response_data == {"Hello": "World"}


@pytest.mark.parametrize(
    "run_fastapi_app_locally, route",
    [(APP, "items"), (APP, "aitems")],
    indirect=["run_fastapi_app_locally"],
)
def test_path_query_params(run_fastapi_app_locally, route):
    url = os.path.join(HTTP_HOST, route, "1")
    headers = {
        "accept": "application/json",
        "Content-Type": "application/json",
    }
    response = requests.get(url, headers=headers, params={"q": "test"})
    response_data = response.json()

    assert response.status_code == 200
    assert response_data == {"item_id": 1, "q": "test"}


@pytest.mark.parametrize(
    "run_fastapi_app_locally, route",
    [(APP, "ws")],
    indirect=["run_fastapi_app_locally"],
)
@pytest.mark.asyncio
async def test_websocket_endpoint(run_fastapi_app_locally, route):
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(os.path.join(WS_HOST, route)) as websocket:
            await websocket.send_json({"interval": 1})
            received_messages = []
            async for message in websocket:
                received_messages.append(message.data)
            assert received_messages == ["0", "1", "2", "3", "4"]


@pytest.mark.parametrize(
    "run_fastapi_app_locally, route",
    [(APP, "sleep")],
    indirect=["run_fastapi_app_locally"],
)
def test_metrics_http(run_fastapi_app_locally, route):
    url = os.path.join(HTTP_HOST, route)
    headers = {
        "accept": "application/json",
        "Content-Type": "application/json",
    }
    response = requests.get(url, headers=headers, params={"interval": 5})
    assert response.status_code == 200

    start_time = time.time()
    examine_request_duration_with_retry(
        start_time,
        expected_value=5,
        route="/" + route,
    )
    examine_request_count_with_retry(
        start_time,
        expected_value=1,
        route="/" + route,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "run_fastapi_app_locally, route",
    [(APP, "ws")],
    indirect=["run_fastapi_app_locally"],
)
async def test_metrics_ws(run_fastapi_app_locally, route):
    async with websockets.connect(os.path.join(WS_HOST, route)) as websocket:
        await websocket.send(json.dumps({"interval": 1}))

        received_messages = []
        for _ in range(5):
            message = await websocket.recv()
            received_messages.append(message)

        assert received_messages == ["0", "1", "2", "3", "4"]

    start_time = time.time()
    examine_request_duration_with_retry(
        start_time,
        expected_value=5,
        route="/" + route,
    )
    examine_request_count_with_retry(
        start_time,
        expected_value=1,
        route="/" + route,
    )
