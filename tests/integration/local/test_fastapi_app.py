import json
import os
import time

import pytest
import requests
import websockets

from ..helper import examine_prom_with_retry, run_fastapi_app_locally

HOST = "localhost:8080"
HTTP_HOST = f"http://{HOST}"
WS_HOST = f"ws://{HOST}"
APP = "tests.integration.fastapi_app.endpoints:app"


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
