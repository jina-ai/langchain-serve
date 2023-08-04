import inspect
import io
import os
from unittest.mock import MagicMock, patch

import pytest

from lcserve.flow import get_flow_dict, get_jcloud_config

file_content_template = """
{instance_line}
{autoscale_min_line}
{disk_size_line}
"""

flow_dict_template = {
    "jtype": "Flow",
    "with": {
        "cors": True,
        "extra_search_paths": ["/workdir/lcserve"],
        "uvicorn_kwargs": {"ws_ping_interval": None, "ws_ping_timeout": None},
        "env": {},
    },
    "gateway": {
        "uses": "jinaai+docker://dummy_image",
        "uses_with": {
            "modules": ["dummy"],
            "fastapi_app_str": "dummy",
            "lcserve_app": False,
        },
        "port": [8080],
        "protocol": [None],
        "uvicorn_kwargs": {"ws_ping_interval": None, "ws_ping_timeout": None},
        "env": {},
        "jcloud": {
            "expose": True,
            "resources": {
                "instance": None,
                "capacity": "spot",
                "storage": {
                    "kind": "efs",
                    "size": "1G",
                },
            },
            "network": {"healthcheck": False},
            "timeout": 120,
            "autoscale": {
                "min": None,
                "max": 10,
                "metric": "rps",
                "target": 10,
                "stable_window": 120,
                "revision_timeout": 120,
            },
        },
    },
    "jcloud": {
        "name": "langchain",
        "docarray": "0.21.0",
        "version": "3.18.0",
        "labels": {"app": "langchain"},
        "monitor": {
            "traces": {"enable": True},
            "metrics": {
                "enable": True,
                "host": "http://opentelemetry-collector.monitor.svc.cluster.local",
                "port": 4317,
            },
        },
    },
}


@pytest.mark.parametrize(
    "instance, autoscale_min, disk_size, expected_instance, expected_autoscale_min, expected_disk_size",
    [
        (None, None, None, "C3", 1, "1G"),
        ("C4", None, None, "C4", 1, "1G"),
        (None, 0, "3G", "C3", 0, "3G"),
        ("C4", 0, "2G", "C4", 0, "2G"),
    ],
)
def test_get_jcloud_config(
    instance,
    autoscale_min,
    expected_instance,
    expected_autoscale_min,
    disk_size,
    expected_disk_size,
    monkeypatch,
):
    # Create the file content based on the parameters
    instance_line = f"instance: {instance}" if instance is not None else ""
    autoscale_min_line = (
        f"autoscale_min: {autoscale_min}" if autoscale_min is not None else ""
    )
    disk_size_line = f"disk_size: {disk_size}" if disk_size is not None else ""

    file_content = file_content_template.format(
        instance_line=instance_line,
        autoscale_min_line=autoscale_min_line,
        disk_size_line=disk_size_line,
    )

    # Use monkeypatch to replace the open function with StringIO
    monkeypatch.setattr("builtins.open", lambda _, __: io.StringIO(file_content))
    monkeypatch.setattr("os.path.exists", lambda _: True)

    result = get_jcloud_config("dummy_file_path")
    assert result.instance == expected_instance
    assert result.autoscale.min == expected_autoscale_min
    assert result.disk_size == expected_disk_size


def test_get_flow_dict_for_local():
    flow_dict = get_flow_dict(
        module_str="dummy",
        fastapi_app_str="dummy",
        jcloud=False,
        is_websocket=False,
    )
    assert flow_dict == {
        "jtype": "Flow",
        "gateway": {
            "uses": os.path.join(
                os.path.dirname(inspect.getfile(get_jcloud_config)),
                "servinggateway_config.yml",
            ),
            "uses_with": {
                "modules": ["dummy"],
                "fastapi_app_str": "dummy",
                "lcserve_app": False,
            },
            "port": [8080],
            "protocol": ["http"],
            "uvicorn_kwargs": {"ws_ping_interval": None, "ws_ping_timeout": None},
            "env": {},
        },
    }


@pytest.mark.parametrize(
    "is_websocket,has_config,instance,autoscale_min,disk_size",
    [
        (
            False,
            True,
            "C5",
            0,
            "1G",
        ),
        (
            True,
            False,
            "C3",
            1,
            "1G",
        ),
        (
            True,
            True,
            "C3",
            2,
            "3G",
        ),
    ],
)
def test_get_flow_dict_for_jcloud(
    is_websocket, has_config, instance, autoscale_min, disk_size, monkeypatch
):
    if has_config:
        instance_line = f"instance: {instance}" if instance is not None else ""
        autoscale_min_line = (
            f"autoscale_min: {autoscale_min}" if autoscale_min is not None else ""
        )
        disk_size_line = f"disk_size: {disk_size}" if disk_size is not None else ""

        file_content = file_content_template.format(
            instance_line=instance_line,
            autoscale_min_line=autoscale_min_line,
            disk_size_line=disk_size_line,
        )
        monkeypatch.setattr("os.path.exists", lambda _: True)
        monkeypatch.setattr("builtins.open", lambda _, __: io.StringIO(file_content))
        flow_dict = get_flow_dict(
            module_str="dummy",
            fastapi_app_str="dummy",
            jcloud=True,
            jcloud_config_path="dummy.yaml",
            is_websocket=is_websocket,
            gateway_id="dummy_image",
        )
    else:
        flow_dict = get_flow_dict(
            module_str="dummy",
            fastapi_app_str="dummy",
            jcloud=True,
            jcloud_config_path=None,
            is_websocket=is_websocket,
            gateway_id="dummy_image",
        )

    flow_dict_template["gateway"]["protocol"][0] = (
        "websocket" if is_websocket else "http"
    )
    flow_dict_template["gateway"]["jcloud"]["autoscale"]["min"] = autoscale_min
    flow_dict_template["gateway"]["jcloud"]["resources"]["instance"] = instance
    flow_dict_template["gateway"]["jcloud"]["resources"]["storage"]["size"] = disk_size

    flow_dict_template["with"]["env"]["LCSERVE_APP_NAME"] = "langchain"
    flow_dict_template["with"]["env"]["LCSERVE_IMAGE"] = "jinaai+docker://dummy_image"
    flow_dict_template["gateway"]["env"]["LCSERVE_APP_NAME"] = "langchain"
    flow_dict_template["gateway"]["env"][
        "LCSERVE_IMAGE"
    ] = "jinaai+docker://dummy_image"

    assert flow_dict == flow_dict_template
