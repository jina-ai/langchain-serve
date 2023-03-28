import logging
import os
import warnings
from typing import List, Union

import click
import yaml


def _ignore_warnings():
    logging.captureWarnings(True)
    warnings.filterwarnings(
        "ignore",
        category=DeprecationWarning,
        message="Deprecated call to `pkg_resources.declare_namespace('google')`.",
    )


_ignore_warnings()


def gateway_config_yaml_path() -> str:
    return os.path.join(os.path.dirname(__file__), 'servinggateway_config.yml')


def flow_config_yaml(apps: Union[str, List[str]], port: int = 12345) -> str:
    if isinstance(apps, str):
        apps = [apps]

    flow_dict = {
        'jtype': 'Flow',
        'gateway': {
            'uses': gateway_config_yaml_path(),
            'uses_with': {
                'modules': apps,
            },
            'port': [port],
            'protocol': ['http'],
        },
    }
    return yaml.safe_dump(flow_dict, sort_keys=False)


def serve_local(apps: Union[str, List[str]], port: int = 12345):
    f_yaml = flow_config_yaml(apps, port)

    from jina import Flow

    with Flow.load_config(f_yaml) as f:
        f.block()


@click.command()
@click.argument(
    'apps',
    nargs=-1,
    type=str,
    required=True,
)
@click.option(
    '--local',
    is_flag=True,
    default=True,
    help='Serve your agent locally',
)
@click.option(
    '--port',
    type=int,
    default=12345,
    help='Port to run the server on',
)
@click.help_option('-h', '--help')
def main(apps, local, port):
    if local:
        serve_local(apps, port)
    else:
        pass


if __name__ == "__main__":
    main()
