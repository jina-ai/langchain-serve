from typing import List, Union

import click
from jina import Flow

from .backend.playground.utils.helper import get_random_tag
from .flow import (
    APP_NAME,
    deploy_app_on_jcloud,
    get_flow_dict,
    get_flow_yaml,
    push_app_to_hubble,
)


def serve_locally(module: Union[str, List[str]], port: int = 8080):
    f_yaml = get_flow_yaml(module, jcloud=False, port=port)
    with Flow.load_config(f_yaml) as f:
        print('Flow started!! ')
        f.block()


def serve_on_jcloud(
    module: Union[str, List[str]],
    name: str = APP_NAME,
    app_id: str = None,
    verbose: bool = False,
):
    tag = get_random_tag()
    gateway_id_wo_tag = push_app_to_hubble(module, name, tag, verbose=verbose)
    app_id, endpoint = deploy_app_on_jcloud(
        flow_dict=get_flow_dict(
            module,
            jcloud=True,
            port=8080,
            name=name,
            gateway_id=gateway_id_wo_tag + ':' + tag,
        ),
        app_id=app_id,
    )
    print(f'App deployed on JCloud with ID: {app_id} with endpoint: {endpoint}')


@click.group()
@click.help_option('-h', '--help')
def serve():
    pass


@serve.command(help='Serve the app locally.')
@click.argument(
    'module',
    type=str,
    required=True,
)
@click.option(
    '--port',
    type=int,
    default=8080,
    help='Port to run the server on.',
)
@click.help_option('-h', '--help')
def local(module, port):
    serve_locally(module, port=port)


@serve.command(help='Serve the app on JCloud.')
@click.argument(
    'module',
    type=str,
    required=True,
)
@click.option(
    '--name',
    type=str,
    default=APP_NAME,
    help='Name of the app.',
    show_default=True,
)
@click.option(
    '--app-id',
    type=str,
    default=None,
    help='AppID of the deployed agent to be updated.',
    show_default=True,
)
@click.option(
    '--verbose',
    is_flag=True,
    help='Verbose mode.',
    show_default=True,
)
@click.help_option('-h', '--help')
def jcloud(module, name, app_id, verbose):
    serve_on_jcloud(module, name=name, app_id=app_id, verbose=verbose)


if __name__ == "__main__":
    serve()
