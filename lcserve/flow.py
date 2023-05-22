import asyncio
import inspect
import os
import secrets
import shutil
import sys
import tempfile
from contextlib import contextmanager
from functools import wraps
from http import HTTPStatus
from importlib import import_module
from shutil import copytree
from tempfile import mkdtemp
from types import ModuleType
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union

import requests
import yaml
from docarray import Document, DocumentArray
from jina import Flow

from .config import get_jcloud_config, DEFAULT_TIMEOUT

if TYPE_CHECKING:
    from fastapi import FastAPI

APP_NAME = 'langchain'
BABYAGI_APP_NAME = 'babyagi'
PDF_QNA_APP_NAME = 'pdfqna'
PANDAS_AI_APP_NAME = 'pandasai'
AUTOGPT_APP_NAME = 'autogpt'

ServingGatewayConfigFile = 'servinggateway_config.yml'
APP_LOGS_URL = "[https://cloud.jina.ai/](https://cloud.jina.ai/user/flows?action=detail&id={app_id}&tab=logs)"


def syncify(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))

    return wrapper


@contextmanager
def StartFlow(protocol, uses, uses_with: Dict = None, port=12345):
    from .backend.playground.utils.helper import parse_uses_with

    with Flow(port=port, protocol=protocol).add(
        uses=uses,
        uses_with=parse_uses_with(uses_with) if uses_with else None,
        env={'JINA_LOG_LEVEL': 'INFO'},
        allow_concurrent=True,
    ) as f:
        yield str(f.protocol).lower() + '://' + f.host + ':' + str(f.port)


@contextmanager
def StartFlowWithPlayground(protocol, uses, uses_with: Dict = None, port=12345):
    from .backend.gateway import PlaygroundGateway
    from .backend.playground.utils.helper import parse_uses_with

    with (
        Flow(port=port)
        .config_gateway(uses=PlaygroundGateway, protocol=protocol)
        .add(
            uses=uses,
            uses_with=parse_uses_with(uses_with) if uses_with else None,
            env={'JINA_LOG_LEVEL': 'INFO'},
            allow_concurrent=True,
        )
    ) as f:
        yield str(f.protocol).lower() + '://' + f.host + ':' + str(f.port)


def ServeGRPC(uses, uses_with: Dict = None, port=12345):
    return StartFlow('grpc', uses, uses_with, port)


def ServeHTTP(uses, uses_with: Dict = None, port=12345):
    return StartFlow('http', uses, uses_with, port)


def ServeWebSocket(uses, uses_with: Dict = None, port=12345):
    return StartFlow('websocket', uses, uses_with, port)


def Interact(host, inputs: Union[str, Dict], output_key='text'):
    from jina import Client

    from .backend.playground.utils.helper import DEFAULT_KEY, RESULT

    if isinstance(inputs, str):
        inputs = {DEFAULT_KEY: inputs}

    # create a document array from inputs as tag
    r = Client(host=host).post(
        on='/run', inputs=DocumentArray([Document(tags=inputs)]), return_responses=True
    )
    if r:
        if len(r) == 1:
            tags = r[0].docs[0].tags
            if output_key in tags:
                return tags[output_key]
            elif RESULT in tags:
                return tags[RESULT]
            else:
                return tags
        else:
            return r


def InteractWithAgent(
    host: str, inputs: str, parameters: Dict, envs: Dict = {}
) -> Union[str, Tuple[str, str]]:
    from jina import Client

    from .backend.playground.utils.helper import (
        AGENT_OUTPUT,
        DEFAULT_KEY,
        RESULT,
        parse_uses_with,
    )

    _parameters = parse_uses_with(parameters)
    if envs and 'env' in _parameters:
        _parameters['env'].update(envs)
    elif envs:
        _parameters['env'] = envs

    # create a document array from inputs as tag
    r = Client(host=host).post(
        on='/load_and_run',
        inputs=DocumentArray([Document(tags={DEFAULT_KEY: inputs})]),
        parameters=_parameters,
        return_responses=True,
    )
    if r:
        if len(r) == 1:
            tags = r[0].docs[0].tags
            if AGENT_OUTPUT in tags and RESULT in tags:
                return tags[RESULT], ''.join(tags[AGENT_OUTPUT])
            elif RESULT in tags:
                return tags[RESULT]
            else:
                return tags
        else:
            return r


def hubble_exists(name: str, secret: Optional[str] = None) -> bool:
    return (
        requests.get(
            url='https://api.hubble.jina.ai/v2/executor/getMeta',
            params={'id': name, 'secret': secret},
        ).status_code
        == HTTPStatus.OK
    )


def _add_to_path(lcserve_app: bool = False):
    # add current directory to the beginning of the path to prioritize local imports
    sys.path.insert(0, os.getcwd())

    if lcserve_app:
        # get all directories in the apps folder and add them to the path
        for app in os.listdir(os.path.join(os.path.dirname(__file__), 'apps')):
            if os.path.isdir(os.path.join(os.path.dirname(__file__), 'apps', app)):
                sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'apps', app))


def _get_parent_dir(modname: str, filename: str) -> str:
    parts = modname.split('.')
    parent_dir = os.path.dirname(filename)
    for _ in range(len(parts) - 1):
        parent_dir = os.path.dirname(parent_dir)
    return parent_dir


def _load_module_from_str(module_str: str):
    try:
        module = import_module(module_str)
    except ModuleNotFoundError:
        print(f'Could not find module {module_str}')
        sys.exit(1)
    except AttributeError:
        print(f'Could not find appdir for module {module_str}')
        sys.exit(1)
    except Exception as e:
        print(f'Unknown error: {e}')
        sys.exit(1)
    return module


def _load_app_from_fastapi_app_str(
    fastapi_app_str: str,
) -> Tuple['FastAPI', ModuleType]:
    from .backend.playground.utils.helper import (
        ImportFromStringError,
        import_from_string,
    )

    try:
        fastapi_app, module = import_from_string(fastapi_app_str)
    except ImportFromStringError as e:
        print(f'Could not import app from {fastapi_app_str}: {e}')
        sys.exit(1)

    return fastapi_app, module


def _any_websocket_route_in_app(app: 'FastAPI') -> bool:
    from fastapi.routing import APIWebSocketRoute

    return any(isinstance(r, APIWebSocketRoute) for r in app.routes)


def _any_websocket_router_in_module(module: ModuleType) -> bool:
    # Go through the module and find all functions decorated by `serving` decorator
    for _, func in inspect.getmembers(module, inspect.isfunction):
        if hasattr(func, '__ws_serving__'):
            return True

    return False


def get_uri(id: str, tag: str):
    import requests

    r = requests.get(f"https://apihubble.jina.ai/v2/executor/getMeta?id={id}&tag={tag}")
    _json = r.json()
    _image_name = _json['data']['name']
    _user_name = _json['meta']['owner']['name']
    return f'jinaai+docker://{_user_name}/{_image_name}:{tag}'


def get_module_dir(
    module_str: str = None,
    fastapi_app_str: str = None,
    app_dir: str = None,
    lcserve_app: bool = False,
) -> Tuple[str, bool]:
    _add_to_path(lcserve_app=lcserve_app)

    if module_str is not None:
        _module = _load_module_from_str(module_str)
        _is_websocket = _any_websocket_router_in_module(_module)
        _module_dir = _get_parent_dir(modname=module_str, filename=_module.__file__)
    elif fastapi_app_str is not None:
        fastapi_app, _module = _load_app_from_fastapi_app_str(fastapi_app_str)
        _is_websocket = _any_websocket_route_in_app(fastapi_app)
        _module_dir = _get_parent_dir(
            modname=fastapi_app_str, filename=_module.__file__
        )

    # if app_dir is not None, return it
    if app_dir is not None:
        return app_dir, _is_websocket

    if not _module.__file__.endswith('.py'):
        print(f'Unknown file type for module {module_str}')
        sys.exit(1)

    return _module_dir, _is_websocket


def _remove_langchain_serve(tmpdir: str) -> None:
    _requirements_txt = 'requirements.txt'
    _pyproject_toml = 'pyproject.toml'

    # Remove langchain-serve itself from the requirements list as a fixed version might break things
    if os.path.exists(os.path.join(tmpdir, _requirements_txt)):
        with open(os.path.join(tmpdir, _requirements_txt), 'r') as f:
            reqs = f.read().splitlines()

        reqs = [r for r in reqs if not r.startswith("langchain-serve")]
        with open(os.path.join(tmpdir, _requirements_txt), 'w') as f:
            f.write('\n'.join(reqs))

    if os.path.exists(os.path.join(tmpdir, _pyproject_toml)):
        import toml

        with open(os.path.join(tmpdir, _pyproject_toml), 'r') as f:
            pyproject = toml.load(f)

        if 'tool' in pyproject and 'poetry' in pyproject['tool']:
            poetry = pyproject['tool']['poetry']
            if 'dependencies' in poetry:
                poetry['dependencies'] = {
                    k: v
                    for k, v in poetry['dependencies'].items()
                    if k != 'langchain-serve'
                }

            if 'dev-dependencies' in poetry:
                poetry['dev-dependencies'] = {
                    k: v
                    for k, v in poetry['dev-dependencies'].items()
                    if k != 'langchain-serve'
                }

        with open(os.path.join(tmpdir, _pyproject_toml), 'w') as f:
            toml.dump(pyproject, f)


def _handle_dependencies(reqs: Tuple[str], tmpdir: str):
    # Create the requirements.txt if requirements are given
    _requirements_txt = 'requirements.txt'
    _pyproject_toml = 'pyproject.toml'

    _existing_requirements = []
    # Get existing requirements and add the new ones
    if os.path.exists(os.path.join(tmpdir, _requirements_txt)):
        with open(os.path.join(tmpdir, _requirements_txt), 'r') as f:
            _existing_requirements = tuple(f.read().splitlines())

    _new_requirements = []
    if reqs is not None:
        for _req in reqs:
            if os.path.isdir(_req):
                if os.path.exists(os.path.join(_req, _requirements_txt)):
                    with open(os.path.join(_req, _requirements_txt), 'r') as f:
                        _new_requirements = f.read().splitlines()

                elif os.path.exists(os.path.join(_req, _pyproject_toml)):
                    # copy pyproject.toml to tmpdir
                    shutil.copyfile(
                        os.path.join(_req, _pyproject_toml),
                        os.path.join(tmpdir, _pyproject_toml),
                    )
            elif os.path.isfile(_req):
                # if it's a file and name is requirements.txt, read it
                if os.path.basename(_req) == _requirements_txt:
                    with open(_req, 'r') as f:
                        _new_requirements = f.read().splitlines()
                elif os.path.basename(_req) == _pyproject_toml:
                    # copy pyproject.toml to tmpdir
                    shutil.copyfile(_req, os.path.join(tmpdir, _pyproject_toml))
            else:
                _new_requirements.append(_req)

        _final_requirements = set(_existing_requirements).union(set(_new_requirements))
        with open(os.path.join(tmpdir, _requirements_txt), 'w') as f:
            f.write('\n'.join(_final_requirements))

    _remove_langchain_serve(tmpdir)


def _handle_dockerfile(tmpdir: str, version: str):
    # if file `lcserve.Dockefile` exists, use it
    _lcserve_dockerfile = 'lcserve.Dockerfile'
    if os.path.exists(os.path.join(tmpdir, _lcserve_dockerfile)):
        shutil.copyfile(
            os.path.join(tmpdir, _lcserve_dockerfile),
            os.path.join(tmpdir, 'Dockerfile'),
        )

        # read the Dockerfile and replace the version
        with open(os.path.join(tmpdir, 'Dockerfile'), 'r') as f:
            dockerfile = f.read()

        dockerfile = dockerfile.replace(
            'jinawolf/serving-gateway:${version}',
            f'jinawolf/serving-gateway:{version}',
        )

        with open(os.path.join(tmpdir, 'Dockerfile'), 'w') as f:
            f.write(dockerfile)

    else:
        # Create the Dockerfile
        with open(os.path.join(tmpdir, 'Dockerfile'), 'w') as f:
            dockerfile = [
                f'FROM jinawolf/serving-gateway:{version}',
                'COPY . /appdir/',
                'RUN if [ -e /appdir/requirements.txt ]; then pip install -r /appdir/requirements.txt; fi',
                'ENTRYPOINT [ "jina", "gateway", "--uses", "config.yml" ]',
            ]
            f.write('\n\n'.join(dockerfile))


def _handle_config_yaml(tmpdir: str, name: str):
    # Create the config.yml
    with open(os.path.join(tmpdir, 'config.yml'), 'w') as f:
        config_dict = {
            'jtype': 'ServingGateway',
            'py_modules': ['lcserve/backend/__init__.py'],
            'metas': {
                'name': name,
            },
        }
        f.write(yaml.safe_dump(config_dict, sort_keys=False))


def _push_to_hubble(
    tmpdir: str, name: str, tag: str, platform: str, verbose: bool
) -> str:
    from hubble.executor.hubio import HubIO
    from hubble.executor.parsers import set_hub_push_parser

    from .backend.playground.utils.helper import EnvironmentVarCtxtManager

    secret = secrets.token_hex(8)
    args_list = [
        tmpdir,
        '--tag',
        tag,
        '--secret',
        secret,
        '--private',
        '--no-usage',
        '--no-cache',
    ]
    if verbose:
        args_list.remove('--no-usage')
        args_list.append('--verbose')

    args = set_hub_push_parser().parse_args(args_list)

    if platform:
        args.platform = platform

    if hubble_exists(name, secret):
        args.force_update = name

    push_envs = (
        {'JINA_HUBBLE_HIDE_EXECUTOR_PUSH_SUCCESS_MSG': 'true'} if not verbose else {}
    )
    with EnvironmentVarCtxtManager(push_envs):
        gateway_id = HubIO(args).push().get('id')
        return gateway_id + ':' + tag


def push_app_to_hubble(
    module_dir: str,
    image_name=None,
    tag: str = 'latest',
    requirements: Tuple[str] = None,
    version: str = 'latest',
    platform: str = None,
    verbose: Optional[bool] = False,
) -> str:
    from .backend.playground.utils.helper import get_random_name

    tmpdir = mkdtemp()

    # Copy appdir to tmpdir
    copytree(module_dir, tmpdir, dirs_exist_ok=True)
    # Copy lcserve to tmpdir
    copytree(
        os.path.dirname(__file__), os.path.join(tmpdir, 'lcserve'), dirs_exist_ok=True
    )

    if image_name is None:
        image_name = get_random_name()
    _handle_dependencies(requirements, tmpdir)
    _handle_dockerfile(tmpdir, version)
    _handle_config_yaml(tmpdir, image_name)
    return _push_to_hubble(tmpdir, image_name, tag, platform, verbose)


def get_gateway_config_yaml_path() -> str:
    return os.path.join(os.path.dirname(__file__), ServingGatewayConfigFile)


def get_gateway_uses(id: str) -> str:
    if id is not None:
        if id.startswith('jinahub+docker') or id.startswith('jinaai+docker'):
            return id
    return f'jinahub+docker://{id}'


def get_existing_name(app_id: str) -> str:
    from jcloud.flow import CloudFlow

    from .backend.playground.utils.helper import asyncio_run_property

    flow_obj = asyncio_run_property(CloudFlow(flow_id=app_id).status)
    if (
        'spec' in flow_obj
        and 'jcloud' in flow_obj['spec']
        and 'name' in flow_obj['spec']['jcloud']
    ):
        return flow_obj['spec']['jcloud']['name']


def get_global_jcloud_args(app_id: str = None, name: str = APP_NAME) -> Dict:
    if app_id is not None:
        _name = get_existing_name(app_id)
        if _name is not None:
            name = _name

    return {
        'jcloud': {
            'name': name,
            'labels': {
                'app': APP_NAME,
            },
            'monitor': {
                'traces': {
                    'enable': True,
                },
                'metrics': {
                    'enable': True,
                    'host': 'http://opentelemetry-collector.monitor.svc.cluster.local',
                    'port': 4317,
                },
            },
        }
    }


def get_uvicorn_args() -> Dict:
    return {
        'uvicorn_kwargs': {
            'ws_ping_interval': None,
            'ws_ping_timeout': None,
        }
    }


def get_with_args_for_jcloud(cors: bool = True) -> Dict:
    return {
        'with': {
            'cors': cors,
            'extra_search_paths': ['/workdir/lcserve'],
            **get_uvicorn_args(),
        }
    }


def get_flow_dict(
    module_str: str = None,
    fastapi_app_str: str = None,
    jcloud: bool = False,
    port: int = 8080,
    name: str = APP_NAME,
    timeout: int = DEFAULT_TIMEOUT,
    app_id: str = None,
    gateway_id: str = None,
    is_websocket: bool = False,
    jcloud_config_path: str = None,
    cors: bool = True,
    lcserve_app: bool = False,
) -> Dict:
    if jcloud:
        jcloud_config = get_jcloud_config(
            config_path=jcloud_config_path, timeout=timeout, is_websocket=is_websocket
        )

    uses = get_gateway_uses(id=gateway_id) if jcloud else get_gateway_config_yaml_path()
    flow_dict = {
        'jtype': 'Flow',
        **(get_with_args_for_jcloud(cors) if jcloud else {}),
        'gateway': {
            'uses': uses,
            'uses_with': {
                'modules': [module_str] if module_str else [],
                'fastapi_app_str': fastapi_app_str or '',
                'lcserve_app': lcserve_app,
            },
            'port': [port],
            'protocol': ['websocket'] if is_websocket else ['http'],
            **get_uvicorn_args(),
            **(jcloud_config.to_dict() if jcloud else {}),
        },
        **(get_global_jcloud_args(app_id=app_id, name=name) if jcloud else {}),
    }
    if os.environ.get("LCSERVE_TEST", False):
        if 'with' not in flow_dict:
            flow_dict['with'] = {}

        flow_dict['with'].update(
            {
                'metrics': True,
                'metrics_exporter_host': 'http://localhost',
                'metrics_exporter_port': 4317,
            }
        )
    return flow_dict


def get_flow_yaml(
    module_str: str = None,
    fastapi_app_str: str = None,
    jcloud: bool = False,
    port: int = 8080,
    name: str = APP_NAME,
    is_websocket: bool = False,
    cors: bool = True,
    jcloud_config_path: str = None,
    lcserve_app: bool = False,
) -> str:
    return yaml.safe_dump(
        get_flow_dict(
            module_str=module_str,
            fastapi_app_str=fastapi_app_str,
            port=port,
            name=name,
            is_websocket=is_websocket,
            cors=cors,
            jcloud=jcloud,
            jcloud_config_path=jcloud_config_path,
            lcserve_app=lcserve_app,
        ),
        sort_keys=False,
    )


async def deploy_app_on_jcloud(
    flow_dict: Dict, app_id: str = None, verbose: bool = False
) -> Tuple[str, str]:
    from .backend.playground.utils.helper import EnvironmentVarCtxtManager

    os.environ['JCLOUD_LOGLEVEL'] = 'INFO' if verbose else 'ERROR'

    from jcloud.flow import CloudFlow

    with tempfile.TemporaryDirectory() as tmpdir:
        flow_path = os.path.join(tmpdir, 'flow.yml')
        with open(flow_path, 'w') as f:
            yaml.safe_dump(flow_dict, f, sort_keys=False)

        deploy_envs = {'JCLOUD_HIDE_SUCCESS_MSG': 'true'} if not verbose else {}
        with EnvironmentVarCtxtManager(deploy_envs):
            if app_id is None:  # appid is None means we are deploying a new app
                jcloud_flow = await CloudFlow(path=flow_path).__aenter__()
                app_id = jcloud_flow.flow_id

            else:  # appid is not None means we are updating an existing app
                jcloud_flow = CloudFlow(path=flow_path, flow_id=app_id)
                await jcloud_flow.update()

        for k, v in jcloud_flow.endpoints.items():
            if k.lower() == 'gateway (http)' or k.lower() == 'gateway (websocket)':
                return app_id, v

    return None, None


async def get_app_status_on_jcloud(app_id: str):
    from jcloud.flow import CloudFlow
    from rich import box
    from rich.align import Align
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.table import Table

    _t = Table(
        'Attribute',
        'Value',
        show_header=False,
        box=box.ROUNDED,
        highlight=True,
        show_lines=True,
    )

    def _add_row(
        key,
        value,
        bold_key: bool = False,
        bold_value: bool = False,
        center_align: bool = True,
    ):
        return _t.add_row(
            Align(f'[bold]{key}' if bold_key else key, vertical='middle'),
            Align(f'[bold]{value}[/bold]' if bold_value else value, align='center')
            if center_align
            else value,
        )

    console = Console()
    with console.status(f'[bold]Getting app status for [green]{app_id}[/green]'):
        app_status = await CloudFlow(flow_id=app_id).status
        if app_status is None:
            return

        if 'status' not in app_status:
            return

        def _get_endpoint(app):
            endpoints = app.get('endpoints', {})
            return list(endpoints.values())[0] if endpoints else ''

        def _replace_wss_with_https(endpoint: str):
            return endpoint.replace('wss://', 'https://')

        status: Dict = app_status['status']
        endpoint = _get_endpoint(status)

        _add_row('App ID', app_id, bold_key=True, bold_value=True)
        _add_row('Phase', status.get('phase', ''))
        _add_row('Endpoint', endpoint)
        _add_row(
            'App logs',
            Markdown(APP_LOGS_URL.format(app_id=app_id), justify='center'),
        )
        _add_row('Swagger UI', _replace_wss_with_https(f'{endpoint}/docs'))
        _add_row('OpenAPI JSON', _replace_wss_with_https(f'{endpoint}/openapi.json'))
        console.print(_t)


async def list_apps_on_jcloud(phase: str, name: str):
    from jcloud.flow import CloudFlow
    from jcloud.helper import cleanup_dt, get_phase_from_response
    from rich import box, print
    from rich.console import Console
    from rich.table import Table

    _t = Table(
        'AppID',
        'Phase',
        'Endpoint',
        'Created',
        box=box.ROUNDED,
        highlight=True,
    )

    console = Console()
    with console.status(f'[bold]Listing all apps'):
        all_apps = await CloudFlow().list_all(
            phase=phase, name=name, labels=f'app={APP_NAME}'
        )
        if not all_apps:
            print('No apps found')
            return

        def _get_endpoint(app):
            endpoints = app.get('status', {}).get('endpoints', {})
            return list(endpoints.values())[0] if endpoints else ''

        for app in all_apps['flows']:
            _t.add_row(
                app['id'],
                get_phase_from_response(app),
                _get_endpoint(app),
                cleanup_dt(app['ctime']),
            )
        console.print(_t)


async def remove_app_on_jcloud(app_id: str) -> None:
    from jcloud.flow import CloudFlow
    from rich import print

    await CloudFlow(flow_id=app_id).__aexit__()
    print(f'App [bold][green]{app_id}[/green][/bold] removed successfully!')


class ImportFromStringError(Exception):
    pass


def load_local_df(module: str):
    from importlib import import_module

    _add_to_path()

    module_str, _, attrs_str = module.partition(":")
    if not module_str or not attrs_str:
        message = (
            'Import string "{import_str}" must be in format "<module>:<attribute>".'
        )
        raise ImportFromStringError(message.format(import_str=module))

    try:
        module = import_module(module_str)
    except ImportError as exc:
        if exc.name != module_str:
            raise exc from None
        message = 'Could not import module "{module_str}".'
        raise ImportFromStringError(message.format(module_str=module_str))

    instance = module
    try:
        for attr_str in attrs_str.split("."):
            instance = getattr(instance, attr_str)
    except AttributeError:
        message = 'Could not import attribute "{attr_str}" from module "{module_str}".'
        raise ImportFromStringError(
            message.format(attr_str=attr_str, module_str=module_str)
        )

    return instance


def update_requirements(path: str, requirements: List[str]) -> List[str]:
    if os.path.exists(path):
        with open(path) as f:
            requirements.extend(f.read().splitlines())

    return requirements


def remove_prefix(text, prefix):
    return text[len(prefix) :] if text.startswith(prefix) else text
