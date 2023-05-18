import inspect
import io
import os
from unittest.mock import MagicMock, patch

import pytest

from lcserve.flow import get_flow_dict, get_jcloud_config

file_content_template = """
{instance_line}
{autoscale_min_line}
"""

flow_dict_template = {
    "jtype": "Flow",
    "with": {
        "cors": True,
        "extra_search_paths": ["/workdir/lcserve"],
        "uvicorn_kwargs": {"ws_ping_interval": None, "ws_ping_timeout": None},
    },
    "gateway": {
        "uses": "jinahub+docker://None",
        "uses_with": {
            "modules": ["dummy"],
            "fastapi_app_str": "dummy",
            "lcserve_app": False,
        },
        "port": [8080],
        "protocol": [None],
        "uvicorn_kwargs": {"ws_ping_interval": None, "ws_ping_timeout": None},
        "jcloud": {
            "expose": True,
            "resources": {"instance": None, "capacity": "spot"},
            "healthcheck": True,
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
    "instance,autoscale_min,expected_instance,expected_autoscale_min",
    [
        (None, None, "C3", 1),
        ("C4", None, "C4", 1),
        (None, 0, "C3", 0),
        ("C4", 0, "C4", 0),
    ],
)
def test_get_jcloud_config(
    instance, autoscale_min, expected_instance, expected_autoscale_min, monkeypatch
):
    # Create the file content based on the parameters
    instance_line = f"instance: {instance}" if instance is not None else ""
    autoscale_min_line = (
        f"autoscale_min: {autoscale_min}" if autoscale_min is not None else ""
    )

    file_content = file_content_template.format(
        instance_line=instance_line, autoscale_min_line=autoscale_min_line
    )

    # Use monkeypatch to replace the open function with StringIO
    monkeypatch.setattr("builtins.open", lambda _, __: io.StringIO(file_content))

    result = get_jcloud_config("dummy_file_path")
    assert result.instance == expected_instance
    assert result.autoscale.min == expected_autoscale_min


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
        },
    }


@pytest.mark.parametrize(
    "is_websocket,has_config,instance,autoscale_min",
    [
        (
            False,
            True,
            "C5",
            0,
        ),
        (
            True,
            False,
            "C3",
            1,
        ),
    ],
)
def test_get_flow_dict_for_jcloud(is_websocket, has_config, instance, autoscale_min):
    if has_config:
        instance_line = f"instance: {instance}" if instance is not None else ""
        autoscale_min_line = (
            f"autoscale_min: {autoscale_min}" if autoscale_min is not None else ""
        )

        file_content = file_content_template.format(
            instance_line=instance_line, autoscale_min_line=autoscale_min_line
        )
        mocked_open = MagicMock()
        mocked_open.return_value.__enter__.return_value = io.StringIO(file_content)
        with patch("builtins.open", mocked_open):
            flow_dict = get_flow_dict(
                module_str="dummy",
                fastapi_app_str="dummy",
                jcloud=True,
                jcloud_config_path="dummy.yaml",
                is_websocket=is_websocket,
            )
    else:
        flow_dict = get_flow_dict(
            module_str="dummy",
            fastapi_app_str="dummy",
            jcloud=True,
            jcloud_config_path=None,
            is_websocket=is_websocket,
        )

    flow_dict_template["gateway"]["protocol"][0] = (
        "websocket" if is_websocket else "http"
    )
    flow_dict_template["gateway"]["jcloud"]["autoscale"]["min"] = autoscale_min
    flow_dict_template["gateway"]["jcloud"]["resources"]["instance"] = instance
    flow_dict_template["gateway"]["jcloud"]["healthcheck"] = not is_websocket

    assert flow_dict == flow_dict_template
