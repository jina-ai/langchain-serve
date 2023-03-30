from typing import List, Union

import click
from jcloud.constants import Phase
from jina import Flow

from .flow import (
    APP_NAME,
    deploy_app_on_jcloud,
    get_app_status_on_jcloud,
    get_flow_dict,
    get_flow_yaml,
    list_apps_on_jcloud,
    push_app_to_hubble,
    remove_app_on_jcloud,
    syncify,
)


def serve_locally(module: Union[str, List[str]], port: int = 8080):
    f_yaml = get_flow_yaml(module, jcloud=False, port=port)
    with Flow.load_config(f_yaml) as f:
        # TODO: add local description
        f.block()


async def serve_on_jcloud(
    module: Union[str, List[str]],
    name: str = APP_NAME,
    app_id: str = None,
    verbose: bool = False,
):
    from .backend.playground.utils.helper import get_random_tag

    tag = get_random_tag()
    gateway_id_wo_tag = push_app_to_hubble(module, tag=tag, verbose=verbose)
    app_id, endpoint = await deploy_app_on_jcloud(
        flow_dict=get_flow_dict(
            module,
            jcloud=True,
            port=8080,
            name=name,
            app_id=app_id,
            gateway_id=gateway_id_wo_tag + ':' + tag,
        ),
        app_id=app_id,
        verbose=verbose,
    )
    await get_app_status_on_jcloud(app_id=app_id)


@click.group()
@click.help_option('-h', '--help')
def serve():
    pass


@serve.group(help='Deploy the app.')
@click.help_option('-h', '--help')
def deploy():
    pass


@deploy.command(help='Deploy the app locally.')
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


@deploy.command(help='Deploy the app on JCloud.')
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
@syncify
async def jcloud(module, name, app_id, verbose):
    await serve_on_jcloud(module, name=name, app_id=app_id, verbose=verbose)


@serve.command(help='List all deployed apps.')
@click.option(
    '--phase',
    type=str,
    default=','.join(
        [
            Phase.Serving,
            Phase.Failed,
            Phase.Starting,
            Phase.Updating,
            Phase.Paused,
        ]
    ),
    help='Deployment phase for the app.',
    show_default=True,
)
@click.option(
    '--name',
    type=str,
    default=None,
    help='Name of the app.',
    show_default=True,
)
@click.help_option('-h', '--help')
@syncify
async def list(phase, name):
    await list_apps_on_jcloud(phase=phase, name=name)


@serve.command(help='Get status of a deployed app.')
@click.argument('app-id')
@click.help_option('-h', '--help')
@syncify
async def status(app_id):
    await get_app_status_on_jcloud(app_id)


@serve.command(help='Remove an app.')
@click.argument('app-id')
@click.help_option('-h', '--help')
@syncify
async def remove(app_id):
    await remove_app_on_jcloud(app_id)


if __name__ == "__main__":
    serve()
