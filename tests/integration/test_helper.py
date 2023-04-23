import logging
import os
import signal
import subprocess
import sys
import time

import psutil
import pytest


@pytest.fixture(scope="session", autouse=True)
def run_test_server(request):
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

    # Start the app
    server_process = subprocess.Popen(
        ["python", "-m", "lcserve", "deploy", "local", app_name], env=env
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
