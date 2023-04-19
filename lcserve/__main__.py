import os
import sys
from typing import List, Union

import click
from jcloud.constants import Phase
from jina import Flow

from . import __version__
from .flow import (
    APP_NAME,
    BABYAGI_APP_NAME,
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
    sys.path.append(os.getcwd())
    f_yaml = get_flow_yaml(module, jcloud=False, port=port)
    with Flow.load_config(f_yaml) as f:
        # TODO: add local description
        f.block()


async def serve_on_jcloud(
    module: Union[str, List[str]],
    name: str = APP_NAME,
    requirements: List[str] = None,
    app_id: str = None,
    version: str = 'latest',
    platform: str = None,
    verbose: bool = False,
):
    from .backend.playground.utils.helper import get_random_tag

    tag = get_random_tag()
    gateway_id_wo_tag, is_websocket = push_app_to_hubble(
        module,
        requirements=requirements,
        tag=tag,
        version=version,
        platform=platform,
        verbose=verbose,
    )
    app_id, endpoint = await deploy_app_on_jcloud(
        flow_dict=get_flow_dict(
            module=module,
            jcloud=True,
            port=8080,
            name=name,
            app_id=app_id,
            gateway_id=gateway_id_wo_tag + ':' + tag,
            websocket=is_websocket,
        ),
        app_id=app_id,
        verbose=verbose,
    )
    await get_app_status_on_jcloud(app_id=app_id)


async def serve_babyagi_on_jcloud(
    name: str = BABYAGI_APP_NAME,
    requirements: List[str] = None,
    app_id: str = None,
    version: str = 'latest',
    platform: str = None,
    verbose: bool = False,
):
    await serve_on_jcloud(
        module='lcserve.apps.babyagi.app',
        name=name,
        requirements=requirements,
        app_id=app_id,
        version=version,
        platform=platform,
        verbose=verbose,
    )


@click.group()
@click.version_option(__version__, '-v', '--version', prog_name='lc-serve')
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
    '--version',
    type=str,
    default='latest',
    help='Version of serving gateway to be used.',
    show_default=False,
)
@click.option(
    '--platform',
    type=str,
    default=None,
    help='Platform of Docker image needed for the deployment is built on.',
    show_default=False,
)
@click.option(
    '--verbose',
    is_flag=True,
    help='Verbose mode.',
    show_default=True,
)
@click.help_option('-h', '--help')
@syncify
async def jcloud(module, name, app_id, version, platform, verbose):
    await serve_on_jcloud(
        module,
        name=name,
        app_id=app_id,
        version=version,
        platform=platform,
        verbose=verbose,
    )


@deploy.command(help='Deploy babyagi on JCloud.')
@click.option(
    '--name',
    type=str,
    default=BABYAGI_APP_NAME,
    help='Name of the app.',
    show_default=True,
)
@click.option(
    '--requirements',
    default=None,
    help='List of requirements to be installed.',
    multiple=True,
)
@click.option(
    '--app-id',
    type=str,
    default=None,
    help='AppID of the deployed agent to be updated.',
    show_default=True,
)
@click.option(
    '--version',
    type=str,
    default='latest',
    help='Version of serving gateway to be used.',
    show_default=False,
)
@click.option(
    '--platform',
    type=str,
    default=None,
    help='Platform of Docker image needed for the deployment is built on.',
    show_default=False,
)
@click.option(
    '--verbose',
    is_flag=True,
    help='Verbose mode.',
    show_default=True,
)
@click.help_option('-h', '--help')
@syncify
async def babyagi(name, requirements, app_id, version, platform, verbose):
    await serve_babyagi_on_jcloud(
        name=name,
        requirements=requirements,
        app_id=app_id,
        version=version,
        platform=platform,
        verbose=verbose,
    )


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


@serve.group(help='Play with predefined apps on JCloud.')
@click.help_option('-h', '--help')
def playground():
    pass


@playground.command(help='Play with babyagi on JCloud.')
def babyagi():
    sys.path.append(os.path.join(os.path.dirname(__file__), 'playground', 'babyagi'))
    from .playground.babyagi.playground import play

    play()


if __name__ == "__main__":
    serve()
