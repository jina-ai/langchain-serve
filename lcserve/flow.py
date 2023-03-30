import asyncio
import os
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from functools import wraps
from http import HTTPStatus
from importlib import import_module
from shutil import copytree
from tempfile import mkdtemp
from typing import Dict, List, Optional, Tuple, Union

import requests
import yaml
from docarray import Document, DocumentArray
from jina import Flow

APP_NAME = 'langchain'
ServingGatewayConfigFile = 'servinggateway_config.yml'
JCloudConfigFile = 'jcloud_config.yml'


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


def push_app_to_hubble(
    mod: str,
    tag: str = 'latest',
    verbose: Optional[bool] = False,
) -> str:
    from hubble.executor.hubio import HubIO
    from hubble.executor.parsers import set_hub_push_parser

    from .backend.playground.utils.helper import get_random_name

    try:
        sys.path.append(os.getcwd())
        file = import_module(mod).__file__
        if file.endswith('.py'):
            appdir = os.path.dirname(file)
        else:
            print(f'Unknown file type for module {mod}')
            sys.exit(1)
    except ModuleNotFoundError:
        print(f'Could not find module {mod}')
        sys.exit(1)
    except AttributeError:
        print(f'Could not find appdir for module {mod}')
        sys.exit(1)
    except Exception as e:
        print(f'Unknown error: {e}')
        sys.exit(1)

    tmpdir = mkdtemp()

    # Copy appdir to tmpdir
    copytree(appdir, tmpdir, dirs_exist_ok=True)
    # Copy lcserve to tmpdir
    copytree(
        os.path.dirname(__file__), os.path.join(tmpdir, 'lcserve'), dirs_exist_ok=True
    )

    name = get_random_name()
    # Create the Dockerfile
    with open(os.path.join(tmpdir, 'Dockerfile'), 'w') as f:
        dockerfile = [
            'FROM jinawolf/serving-gateway:latest',
            'COPY . /appdir/',
            'RUN if [ -e /appdir/requirements.txt ]; then pip install -r /appdir/requirements.txt; fi',
            'ENTRYPOINT [ "jina", "gateway", "--uses", "config.yml" ]',
        ]
        f.write('\n\n'.join(dockerfile))

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

    args_list = [
        tmpdir,
        '--tag',
        tag,
        '--secret',
        'somesecret',
        '--public',
        '--no-usage',
        '--no-cache',
    ]
    if verbose:
        args_list.remove('--no-usage')
        args_list.append('--verbose')

    args = set_hub_push_parser().parse_args(args_list)

    if hubble_exists(name):
        args.force_update = name

    return HubIO(args).push().get('id')


@dataclass
class Defaults:
    instance: str = 'C2'
    autoscale_min: int = 0
    autoscale_max: int = 10
    autoscale_rps: int = 10

    def __post_init__(self):
        # read from config yaml
        with open(os.path.join(os.getcwd(), JCloudConfigFile), 'r') as fp:
            config = yaml.safe_load(fp.read())
            self.instance = config.get('instance', self.instance)
            self.autoscale_min = config.get('autoscale', {}).get(
                'min', self.autoscale_min
            )
            self.autoscale_max = config.get('autoscale', {}).get(
                'max', self.autoscale_max
            )
            self.autoscale_rps = config.get('autoscale', {}).get(
                'rps', self.autoscale_rps
            )


def get_gateway_config_yaml_path() -> str:
    return os.path.join(os.path.dirname(__file__), ServingGatewayConfigFile)


def get_gateway_uses(id: str) -> str:
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
                },
            },
        }
    }


@dataclass
class AutoscaleConfig:
    min: int = Defaults.autoscale_min
    max: int = Defaults.autoscale_max
    rps: int = Defaults.autoscale_rps

    def to_dict(self) -> Dict:
        return {
            'autoscale': {
                'min': self.min,
                'max': self.max,
                'metric': 'rps',
                'target': self.rps,
            }
        }


def get_with_args_for_jcloud() -> Dict:
    return {
        'with': {
            'extra_search_paths': ['/workdir/lcserve'],
        }
    }


def get_gateway_jcloud_args(
    instance: str = Defaults.instance,
    autoscale: AutoscaleConfig = AutoscaleConfig(),
) -> Dict:
    return {
        'jcloud': {
            'expose': True,
            'resources': {
                'instance': instance,
                'capacity': 'spot',
            },
            **(autoscale.to_dict() if autoscale else {}),
        }
    }


def get_flow_dict(
    module: Union[str, List[str]],
    jcloud: bool = False,
    port: int = 8080,
    name: str = APP_NAME,
    app_id: str = None,
    gateway_id: str = None,
) -> Dict:
    if isinstance(module, str):
        module = [module]

    uses = get_gateway_uses(id=gateway_id) if jcloud else get_gateway_config_yaml_path()
    return {
        'jtype': 'Flow',
        **(get_with_args_for_jcloud() if jcloud else {}),
        'gateway': {
            'uses': uses,
            'uses_with': {
                'modules': module,
            },
            'port': [port],
            'protocol': ['http'],
            **(get_gateway_jcloud_args() if jcloud else {}),
        },
        **(get_global_jcloud_args(app_id=app_id, name=name) if jcloud else {}),
    }


def get_flow_yaml(
    module: Union[str, List[str]],
    jcloud: bool = False,
    port: int = 8080,
    name: str = APP_NAME,
) -> str:
    return yaml.safe_dump(
        get_flow_dict(module=module, jcloud=jcloud, port=port, name=name),
        sort_keys=False,
    )


async def deploy_app_on_jcloud(
    flow_dict: Dict, app_id: str = None, verbose: bool = False
) -> Tuple[str, str]:
    os.environ['JCLOUD_LOGLEVEL'] = 'INFO' if verbose else 'ERROR'

    from jcloud.flow import CloudFlow

    with tempfile.TemporaryDirectory() as tmpdir:
        flow_path = os.path.join(tmpdir, 'flow.yml')
        with open(flow_path, 'w') as f:
            yaml.safe_dump(flow_dict, f, sort_keys=False)

        if app_id is None:  # appid is None means we are deploying a new app
            jcloud_flow = await CloudFlow(path=flow_path).__aenter__()
            app_id = jcloud_flow.flow_id

        else:  # appid is not None means we are updating an existing app
            jcloud_flow = CloudFlow(path=flow_path, flow_id=app_id)
            await jcloud_flow.update()

        for k, v in jcloud_flow.endpoints.items():
            if k.lower() == 'gateway (http)':
                return app_id, v

    return None, None


async def get_app_status_on_jcloud(app_id: str):
    from jcloud.flow import CloudFlow
    from rich import box
    from rich.align import Align
    from rich.console import Console
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
        flow_status = await CloudFlow(flow_id=app_id).status
        if 'status' not in flow_status:
            return

        status: Dict = flow_status['status']
        endpoint = status.get('endpoints', {}).get('gateway (http)', '')
        _add_row('AppID', app_id, bold_key=True, bold_value=True)
        _add_row('Phase', status.get('phase', ''))
        _add_row('Endpoint', endpoint)
        _add_row('Swagger UI', f'{endpoint}/docs')
        _add_row('OpenAPI JSON', f'{endpoint}/openapi.json')
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

        for app in all_apps['flows']:
            _t.add_row(
                app['id'],
                get_phase_from_response(app),
                app.get('status', {}).get('endpoints', {}).get('gateway (http)', ''),
                cleanup_dt(app['ctime']),
            )
        console.print(_t)


async def remove_app_on_jcloud(app_id: str) -> None:
    from jcloud.flow import CloudFlow
    from rich import print

    await CloudFlow(flow_id=app_id).__aexit__()
    print(f'App [bold][green]{app_id}[/green][/bold] removed successfully!')
