import os
import json

import pytest
import requests
import websockets

from .helper import run_test_server

HOST = 'localhost:8080'
HTTP_HOST = f'http://{HOST}'
WS_HOST = f'ws://{HOST}'


@pytest.mark.parametrize(
    "run_test_server, route",
    [("basic_app", "sync_http"), ("basic_app", "async_http")],
    indirect=["run_test_server"],
)
def test_basic_app_http(run_test_server, route):
    url = os.path.join(HTTP_HOST, route)
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
    async with websockets.connect(WS_HOST + route) as websocket:
        await websocket.send(json.dumps({"interval": 1}))

        received_messages = []
        for _ in range(5):
            message = await websocket.recv()
            received_messages.append(message)

        assert received_messages == ["0", "1", "2", "3", "4"]


@pytest.mark.parametrize(
    "run_test_server, route",
    [("basic_app", "sync_auth_http")],
    indirect=["run_test_server"],
)
def test_basic_app_http_authorized(run_test_server, route):
    url = os.path.join(HTTP_HOST, route)
    data = {"interval": 1, "envs": {}}

    # no auth headers
    response = requests.post(url, json=data)
    assert response.status_code == 403
    assert response.json()["detail"] == "Not authenticated"

    # not a bearer token
    response = requests.post(url, headers={'Authorization': 'invalidtoken'}, json=data)
    assert response.status_code == 403
    assert response.json()["detail"] == "Not authenticated"

    # invalid bearer token
    response = requests.post(
        url, headers={'Authorization': 'Bearer invalidtoken'}, json=data
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid bearer token"

    # valid bearer token
    response = requests.post(
        url, headers={'Authorization': 'Bearer mysecrettoken'}, json=data
    )

    assert response.status_code == 200
    assert response.json()["result"] == "Hello, world!"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "run_test_server, route",
    [("basic_app", "sync_auth_ws")],
    indirect=["run_test_server"],
)
async def test_basic_app_ws_authorized(run_test_server, route):
    url = os.path.join(WS_HOST, route)

    # no auth headers
    with pytest.raises(websockets.InvalidStatusCode) as e:
        async with websockets.connect(url) as websocket:
            pass

    assert e.value.status_code == 403

    # not a bearer token
    with pytest.raises(websockets.InvalidStatusCode) as e:
        async with websockets.connect(
            url, extra_headers={'Authorization': 'invalidtoken'}
        ) as websocket:
            pass

    assert e.value.status_code == 403

    # invalid bearer token
    with pytest.raises(websockets.InvalidStatusCode) as e:
        async with websockets.connect(
            url, extra_headers={'Authorization': 'Bearer invalidtoken'}
        ) as websocket:
            pass

    assert e.value.status_code == 403

    # valid bearer token
    async with websockets.connect(
        url, extra_headers={'Authorization': 'Bearer mysecrettoken'}
    ) as websocket:
        await websocket.send(json.dumps({"interval": 1}))

        received_messages = []
        for _ in range(5):
            message = await websocket.recv()
            received_messages.append(message)

        assert received_messages == ["0", "1", "2", "3", "4"]
