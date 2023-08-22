import json
import os
import time

import pytest
import requests
import websockets

from ..helper import (
    assert_jaeger_tracing_data,
    examine_request_count_with_retry,
    examine_request_duration_with_retry,
    run_test_app_locally,
)

HOST = "localhost:8000"
HTTP_HOST = f"http://{HOST}"
WS_HOST = f"ws://{HOST}"


@pytest.mark.parametrize(
    "run_test_app_locally, route",
    [("basic_app", "sync_http"), ("basic_app", "async_http")],
    indirect=["run_test_app_locally"],
)
def test_basic_app_http(run_test_app_locally, route):
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
    "run_test_app_locally, route",
    [("basic_app", "sync_ws"), ("basic_app", "async_ws")],
    indirect=["run_test_app_locally"],
)
async def test_basic_app_ws(run_test_app_locally, route):
    async with websockets.connect(os.path.join(WS_HOST, route)) as websocket:
        await websocket.send(json.dumps({"interval": 1}))

        received_messages = []
        for _ in range(5):
            message = await websocket.recv()
            received_messages.append(message)

        assert received_messages == ["0", "1", "2", "3", "4"]


@pytest.mark.parametrize(
    "run_test_app_locally, route",
    [
        ("basic_app", "sync_auth_http"),
        ("basic_app", "sync_auth_http_auth_response"),
    ],
    indirect=["run_test_app_locally"],
)
def test_basic_app_http_authorized(run_test_app_locally, route):
    url = os.path.join(HTTP_HOST, route)
    data = {"interval": 1, "envs": {}}

    # no auth headers
    response = requests.post(url, json=data)
    assert response.status_code == 403
    assert response.json()["detail"] == "Not authenticated"

    # not a bearer token
    response = requests.post(url, headers={"Authorization": "invalidtoken"}, json=data)
    assert response.status_code == 403
    assert response.json()["detail"] == "Not authenticated"

    # invalid bearer token
    response = requests.post(
        url, headers={"Authorization": "Bearer invalidtoken"}, json=data
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid bearer token"

    # valid bearer token
    response = requests.post(
        url, headers={"Authorization": "Bearer mysecrettoken"}, json=data
    )

    assert response.status_code == 200
    assert response.json()["result"] == "Hello, world!"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "run_test_app_locally, route",
    [
        ("basic_app", "sync_auth_ws"),
        ("basic_app", "sync_auth_ws_auth_response"),
    ],
    indirect=["run_test_app_locally"],
)
async def test_basic_app_ws_authorized(run_test_app_locally, route):
    url = os.path.join(WS_HOST, route)

    # no auth headers
    with pytest.raises(websockets.InvalidStatusCode) as e:
        async with websockets.connect(url) as websocket:
            pass

    assert e.value.status_code == 403

    # not a bearer token
    with pytest.raises(websockets.InvalidStatusCode) as e:
        async with websockets.connect(
            url, extra_headers={"Authorization": "invalidtoken"}
        ) as websocket:
            pass

    assert e.value.status_code == 403

    # invalid bearer token
    with pytest.raises(websockets.InvalidStatusCode) as e:
        async with websockets.connect(
            url, extra_headers={"Authorization": "Bearer invalidtoken"}
        ) as websocket:
            pass

    assert e.value.status_code == 403

    # valid bearer token
    async with websockets.connect(
        url, extra_headers={"Authorization": "Bearer mysecrettoken"}
    ) as websocket:
        await websocket.send(json.dumps({"interval": 1}))

        received_messages = []
        for _ in range(5):
            message = await websocket.recv()
            received_messages.append(message)

        assert received_messages == ["0", "1", "2", "3", "4"]


@pytest.mark.parametrize(
    "run_test_app_locally",
    [("basic_app")],
    indirect=["run_test_app_locally"],
)
def test_single_file_upload_http(run_test_app_locally):
    url = os.path.join(HTTP_HOST, "single_file_upload")
    with open(__file__, "rb") as f:
        response = requests.post(
            url,
            files={"file": f},
            params={"input_data": "{}"},
        )

        response_data = response.json()
        assert response.status_code == 200
        assert response_data["result"] == "test_basic_app.py"


@pytest.mark.parametrize(
    "run_test_app_locally",
    [("basic_app")],
    indirect=["run_test_app_locally"],
)
def test_single_file_upload_with_extra_arg_http(run_test_app_locally):
    url = os.path.join(HTTP_HOST, "single_file_upload_with_extra_arg")
    with open(__file__, "rb") as f:
        response = requests.post(
            url,
            files={"file": f},
            params={
                "input_data": json.dumps(
                    {
                        "question": "what is the file name?",
                        "someint": 1,
                        "envs": {"A": "B"},
                    }
                ),
            },
        )
        response_data = response.json()
        assert response.status_code == 200
        assert response_data["result"] == {
            "file": "test_basic_app.py",
            "question": "what is the file name?",
            "someint": "1",
        }


@pytest.mark.parametrize(
    "run_test_app_locally",
    [("basic_app")],
    indirect=["run_test_app_locally"],
)
def test_multiple_file_uploads_http(run_test_app_locally):
    url = os.path.join(HTTP_HOST, "multiple_file_uploads")

    _init_file = os.path.join(os.path.dirname(__file__), "__init__.py")
    with open(__file__, "rb") as f1, open(_init_file, "rb") as f2:
        response = requests.post(
            url,
            files={"f1": f1, "f2": f2},
            params={"input_data": "{}"},
        )
        response_data = response.json()
        assert response.status_code == 200
        assert response_data["result"] == ["test_basic_app.py", "__init__.py"]


@pytest.mark.parametrize(
    "run_test_app_locally",
    [("basic_app")],
    indirect=["run_test_app_locally"],
)
def test_multiple_file_uploads_with_extra_arg_http(run_test_app_locally):
    url = os.path.join(HTTP_HOST, "multiple_file_uploads_with_extra_arg")

    _init_file = os.path.join(os.path.dirname(__file__), "__init__.py")
    with open(__file__, "rb") as f1, open(_init_file, "rb") as f2:
        response = requests.post(
            url,
            files={"f1": f1, "f2": f2},
            params={
                "input_data": json.dumps(
                    {
                        "question": "what is the file name?",
                        "someint": 1,
                        "envs": {"A": "B"},
                    }
                ),
            },
        )
        response_data = response.json()
        assert response.status_code == 200
        assert response_data["result"] == {
            "f1": "test_basic_app.py",
            "f2": "__init__.py",
            "question": "what is the file name?",
            "someint": "1",
        }


@pytest.mark.parametrize(
    "run_test_app_locally, route",
    [("basic_app", "sync_http")],
    indirect=["run_test_app_locally"],
)
def test_metrics_http(run_test_app_locally, route):
    url = os.path.join(HTTP_HOST, route)
    headers = {
        "accept": "application/json",
        "Content-Type": "application/json",
    }
    data = {"interval": 5, "envs": {}}
    response = requests.post(url, headers=headers, json=data)
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
    "run_test_app_locally, route",
    [("basic_app", "sync_ws")],
    indirect=["run_test_app_locally"],
)
async def test_metrics_ws(run_test_app_locally, route):
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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "run_test_app_locally",
    [("basic_app")],
    indirect=["run_test_app_locally"],
)
async def test_workspace(run_test_app_locally):
    http_url = os.path.join(HTTP_HOST, "store")
    ws_url = os.path.join(WS_HOST, "stream")

    for i in range(10):
        data = {"text": f"Here's string {i}", "envs": {}}
        response = requests.post(http_url, json=data)
        assert response.status_code == 200

    async with websockets.connect(ws_url) as websocket:
        await websocket.send(json.dumps({}))

        received_messages = []
        for _ in range(10):
            message = await websocket.recv()
            received_messages.append(message.strip())

        assert received_messages == [f"Here's string {i}" for i in range(10)]


@pytest.mark.parametrize(
    "run_test_app_locally, route",
    [("basic_app", "tracing")],
    indirect=["run_test_app_locally"],
)
def test_tracing_http(run_test_app_locally, route):
    url = os.path.join(HTTP_HOST, route)
    headers = {
        "accept": "application/json",
        "Content-Type": "application/json",
    }
    data = {"dummy": "dummy string", "envs": {}}
    response = requests.post(url, headers=headers, json=data)
    assert response.status_code == 200
    assert_jaeger_tracing_data("gateway/rep-0", "dummy string")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "run_test_app_locally, route",
    [("basic_app", "tracing_ws")],
    indirect=["run_test_app_locally"],
)
async def test_tracing_ws(run_test_app_locally, route):
    async with websockets.connect(os.path.join(WS_HOST, route)) as websocket:
        await websocket.send(json.dumps({"dummy": "dummy string ws"}))
        message = await websocket.recv()

    assert "dummy string ws" in message
    assert_jaeger_tracing_data("gateway/rep-0", "dummy string ws")
