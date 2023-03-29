import sys
from typing import List, Union

import click
from jina import Flow

from .flow import deploy_app_on_jcloud, get_flow_dict, get_flow_yaml, push_app_to_hubble


def serve_locally(module: Union[str, List[str]], port: int = 8080):
    f_yaml = get_flow_yaml(module, jcloud=False, port=port)
    with Flow.load_config(f_yaml) as f:
        print('Flow started!! ')
        f.block()


def serve_on_jcloud(
    module: Union[str, List[str]],
    name: str = 'langchain',
    verbose: bool = False,
):
    gateway_id = push_app_to_hubble(module, name, 'latest', verbose=verbose)
    deploy_app_on_jcloud(
        get_flow_dict(
            module,
            jcloud=True,
            port=8080,
            name=name,
            gateway_id=gateway_id,
        )
    )


@click.command()
@click.argument(
    'module',
    type=str,
    required=True,
)
@click.option(
    '--local',
    is_flag=True,
    help='Serve your agent locally',
)
@click.option(
    '--jcloud',
    is_flag=True,
    help='Serve your agent on jcloud',
)
@click.option(
    '--name',
    type=str,
    default=None,
    help='Name of the agent',
)
@click.option(
    '--port',
    type=int,
    default=8080,
    help='Port to run the server on',
)
@click.option(
    '--verbose',
    is_flag=True,
    help='Verbose mode',
)
@click.help_option('-h', '--help')
def main(module, local, jcloud, name, port, verbose):
    if local and jcloud:
        click.echo('--local and --jcloud are mutually exclusive')
        sys.exit(1)
    elif local:
        serve_locally(module, port=port)
    else:
        serve_on_jcloud(module, name=name, verbose=verbose)


if __name__ == "__main__":
    main()
