import asyncio
import logging
import os
import platform
import signal
import subprocess
import sys
import time
from contextlib import asynccontextmanager

import psutil
import pytest
import requests

from lcserve.__main__ import remove_app_on_jcloud, serve_on_jcloud

PROMETHEUS_URL = "http://localhost:9090"
JAEGER_URL = "http://localhost:16686"


async def _serve_on_jcloud(**deployment_args):
    # This handle is for Hubble push
    if platform.machine() == 'arm64':
        deployment_args["platform"] = "linux/amd64"

    logging.info("Deploying the test app to JCloud ...")
    app_id = await serve_on_jcloud(**deployment_args)

    # In case endpoints are not available for whatever reason
    await asyncio.sleep(20)
    return app_id


@asynccontextmanager
async def deploy_jcloud_app(**deployment_args):
    # Make sure apps folder is discoverable
    apps_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'apps')
    sys.path.append(apps_path)

    deployment_args["module_str"] = "basic_app"
    app_id = await _serve_on_jcloud(**deployment_args)
    # Since we don't do hc for the Flow, let's wait for a while for it to be ready
    asyncio.sleep(60)

    try:
        yield app_id
    finally:
        logging.info("Cleanup the test app ...")
        await remove_app_on_jcloud(app_id)


@asynccontextmanager
async def deploy_jcloud_fastapi_app(**deployment_args):
    # Make sure apps folder is discoverable
    apps_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'fastapi_app')
    sys.path.append(apps_path)

    deployment_args.update(
        {
            "fastapi_app_str": "endpoints:app",
            "app_dir": apps_path,
        }
    )
    app_id = await _serve_on_jcloud(**deployment_args)

    try:
        yield app_id
    finally:
        logging.info("Cleanup the test app ...")
        await remove_app_on_jcloud(app_id)


@pytest.fixture(scope="session", autouse=True)
def run_test_app_locally(request):
    app_name = request.param

    # Make sure apps folder is discoverable
    apps_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'apps')
    sys.path.append(apps_path)

    env = os.environ.copy()
    env["PYTHONPATH"] = (
        apps_path
        + (os.pathsep if env.get("PYTHONPATH") else "")
        + env.get("PYTHONPATH", "")
    )
    # Mark LCSERVE_TEST as true to make the Flow tested export metrics (to docker composed monitor stack)
    env["LCSERVE_TEST"] = "true"

    # Start the app
    server_process = subprocess.Popen(
        ["python", "-m", "lcserve", "deploy", "local", app_name, "--port", "8000"],
        env=env,
    )
    logging.info(f"Wait 10s for app [{app_name}] to be ready ...")
    time.sleep(10)  # Give the server some time to start
    logging.info("Tests starts ...")

    yield

    # Clean up
    logging.info("Cleanup the app processes ...")
    kill_child_pids(server_process.pid)
    logging.info("Done!!")


@pytest.fixture(scope="session", autouse=True)
def run_fastapi_app_locally(request):
    app_name = request.param

    # Make sure apps folder is discoverable
    apps_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'fastapi_app')
    sys.path.append(apps_path)

    env = os.environ.copy()
    env["PYTHONPATH"] = (
        apps_path
        + (os.pathsep if env.get("PYTHONPATH") else "")
        + env.get("PYTHONPATH", "")
    )
    # Mark LCSERVE_TEST as true to make the Flow tested export metrics (to docker composed monitor stack)
    env["LCSERVE_TEST"] = "true"

    # Start the app
    server_process = subprocess.Popen(
        ["python", "-m", "lcserve", "deploy", "local", "--app", app_name], env=env
    )
    logging.info(f"Wait 10s for app [{app_name}] to be ready ...")
    time.sleep(10)  # Give the server some time to start
    logging.info("Tests starts ...")

    yield

    # Clean up
    logging.info("Cleanup the app processes ...")
    kill_child_pids(server_process.pid)
    logging.info("Done!!")


def kill_child_pids(pid):
    parent = psutil.Process(pid)
    children = parent.children(recursive=True)
    for child in children:
        os.kill(child.pid, signal.SIGTERM)


def get_values_from_prom(metrics, route):
    response = requests.get(
        f"{PROMETHEUS_URL}/api/v1/query",
        params={"query": metrics},
    )
    assert response.status_code == 200

    try:
        metrics = [
            metric
            for metric in response.json()["data"]["result"]
            if metric['metric']['route'] == route
        ]

        # Fetch the latest metric at index 0 from metrics
        duration_seconds = metrics[0]['value'][1]
    except:
        duration_seconds = 0
    return duration_seconds


def assert_jaeger_tracing_data(service, expected_string):
    # Wait for Jaeger gets populated
    time.sleep(30)
    response = requests.get(
        f"{JAEGER_URL}/api/traces?service={service}",
    )
    spans = []
    try:
        traces = response.json()["data"]
        for trace in traces:
            spans.extend(trace["spans"])
    except:
        assert False

    for span in spans:
        for log in span["logs"]:
            for field in log["fields"]:
                if field["key"] == "data" and field["type"] == "string":
                    if expected_string in field["value"]:
                        assert True
                        return

    assert False


def examine_request_duration_with_retry(start_time, expected_value, route):
    timeout = 120
    interval = 10

    while True:
        elapsed_time = time.time() - start_time
        if elapsed_time > timeout:
            pytest.fail("Timed out waiting for the Prometheus data to be populated")

        duration_seconds = get_values_from_prom(
            "lcserve_request_duration_seconds", route
        )
        if round(float(duration_seconds)) == expected_value:
            break

        time.sleep(interval)


def examine_request_count_with_retry(start_time, expected_value, route):
    timeout = 120
    interval = 10

    while True:
        elapsed_time = time.time() - start_time
        if elapsed_time > timeout:
            pytest.fail("Timed out waiting for the Prometheus data to be populated")

        request_count = get_values_from_prom("lcserve_request_count", route)
        if float(request_count) == expected_value:
            break

        time.sleep(interval)
