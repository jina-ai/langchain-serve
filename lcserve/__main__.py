import sys
from typing import List, Union

import click
import yaml
from jina import Flow

from .flow import get_flow_dict, get_flow_yaml, serve_on_jcloud


def serve_local(mods: Union[str, List[str]], port: int = 8080):
    f_yaml = get_flow_yaml(mods, jcloud=False, port=port)
    with Flow.load_config(f_yaml) as f:
        print('Flow started!! ')
        f.block()


def serve_jcloud(mods: Union[str, List[str]]):
    serve_on_jcloud(get_flow_dict(mods, jcloud=True, port=8080))


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
    help='Serve your agent locally',
)
@click.option(
    '--jcloud',
    is_flag=True,
    help='Serve your agent on jcloud',
)
@click.option(
    '--port',
    type=int,
    default=8080,
    help='Port to run the server on',
)
@click.help_option('-h', '--help')
def main(mods, local, jcloud, port):
    if local and jcloud:
        click.echo('--local and --jcloud are mutually exclusive')
        sys.exit(1)
    elif local:
        serve_local(mods, port)
    else:
        serve_jcloud(mods)


if __name__ == "__main__":
    main()
