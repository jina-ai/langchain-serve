import pytest
import requests

from .test_helper import run_test_server


@pytest.mark.parametrize(
    "run_test_server, route",
    [("sync_http_app", "sync_http"), ("async_http_app", "async_http")],
    indirect=["run_test_server"],
)
def test_app(run_test_server, route):
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
