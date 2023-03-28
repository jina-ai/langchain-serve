import os
from typing import List, Union

import click
import yaml

ServingGatewayConfigFile = 'servinggateway_config.yml'


def gateway_config_yaml_path() -> str:
    return os.path.join(os.path.dirname(__file__), ServingGatewayConfigFile)


def gateway_docker_image() -> str:
    return 'docker://jinawolf/12345-gateway:latest'


def flow_yaml(
    mods: Union[str, List[str]],
    local: bool = True,
    port: int = 12345,
) -> str:
    if isinstance(mods, str):
        mods = [mods]

    flow_dict = {
        'jtype': 'Flow',
        'gateway': {
            'uses': gateway_config_yaml_path() if local else gateway_docker_image(),
            'uses_with': {
                'modules': mods,
            },
            'port': [port],
            'protocol': ['http'],
        },
    }
    return yaml.safe_dump(flow_dict, sort_keys=False)


def serve_local(mods: Union[str, List[str]], port: int = 12345):
    f_yaml = flow_yaml(mods, port)

    print(f'Loading Flow from config:\n{f_yaml}')
    from jina import Flow

    with Flow.load_config(f_yaml) as f:
        f.block()


def serve_jcloud(mods: Union[str, List[str]]):
    f_yaml = flow_yaml(mods, local=False)

    print(f'Loading Flow from config:\n{f_yaml}')
    from jina import Flow

    with Flow.load_config(f_yaml) as f:
        f.block()


@click.command()
@click.argument(
    'mods',
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
def main(mods, local, port):
    if local:
        serve_local(mods, port)
    else:
        serve_jcloud(mods)


if __name__ == "__main__":
    main()
