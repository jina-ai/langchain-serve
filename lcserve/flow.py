import asyncio
import inspect
import os
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import wraps
from http import HTTPStatus
from importlib import import_module
from shutil import copytree
from tempfile import mkdtemp
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import requests
import yaml
from docarray import Document, DocumentArray
from jina import Flow

from .errors import InvalidAutoscaleMinError, InvalidInstanceError
from .utils import validate_jcloud_config

APP_NAME = 'langchain'
BABYAGI_APP_NAME = 'babyagi'
PDF_QNA_APP_NAME = 'pdfqna'
PANDAS_AI_APP_NAME = 'pandasai'
AUTOGPT_APP_NAME = 'autogpt'
DEFAULT_TIMEOUT = 120
ServingGatewayConfigFile = 'servinggateway_config.yml'
JCloudConfigFile = 'jcloud_config.yml'
# TODO: this needs to be pulled from Jina Wolf API dynamically after the issue has been fixed on the API side
APP_LOGS_URL = "[dashboards.wolf.jina.ai](https://dashboard.wolf.jina.ai/d/flow/flow-monitor?var-flow={flow}&var-datasource=thanos&orgId=2&from=now-24h&to=now&viewPanel=85)"


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


def _any_websocket_router(app) -> bool:
    # Go through the module and find all functions decorated by `serving` decorator
    for _, func in inspect.getmembers(app, inspect.isfunction):
        if hasattr(func, '__ws_serving__'):
            return True

    return False


def _add_to_path():
    sys.path.append(os.getcwd())
    # get all directories in the apps folder and add them to the path
    for app in os.listdir(os.path.join(os.path.dirname(__file__), 'apps')):
        sys.path.append(os.path.join(os.path.dirname(__file__), 'apps', app))


def _get_parent_dir(modname: str, filename: str) -> str:
    parts = modname.split('.')
    parent_dir = os.path.dirname(filename)
    for _ in range(len(parts) - 1):
        parent_dir = os.path.dirname(parent_dir)
    return parent_dir


def get_app_dir(mod):
    try:
        _add_to_path()
        app = import_module(mod)
        file = app.__file__
        if file.endswith('.py'):
            return app, _get_parent_dir(mod, file)
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


def resolve_jcloud_config(config, app_dir):
    # config given from CLI takes higher priority
    if config:
        return config

    # Check to see if jcloud YAML/YML file exists at app dir
    config_path_yml = os.path.join(app_dir, "jcloud.yml")
    config_path_yaml = os.path.join(app_dir, "jcloud.yaml")

    if os.path.exists(config_path_yml):
        config_path = config_path_yml
    elif os.path.exists(config_path_yaml):
        config_path = config_path_yaml
    else:
        return None

    try:
        validate_jcloud_config(config_path)
    except (InvalidAutoscaleMinError, InvalidInstanceError):
        # If it's malformed, we treated as non-existed
        return None

    print(f'JCloud config file at app directory will be applied: {config_path}')
    return config_path


def push_app_to_hubble(
    app: Any,
    app_dir: str,
    tag: str = 'latest',
    requirements: Tuple[str] = None,
    version: str = 'latest',
    platform: str = None,
    verbose: Optional[bool] = False,
) -> Tuple[str, bool]:
    from hubble.executor.hubio import HubIO
    from hubble.executor.parsers import set_hub_push_parser

    from .backend.playground.utils.helper import get_random_name

    tmpdir = mkdtemp()

    # Copy appdir to tmpdir
    copytree(app_dir, tmpdir, dirs_exist_ok=True)
    # Copy lcserve to tmpdir
    copytree(
        os.path.dirname(__file__), os.path.join(tmpdir, 'lcserve'), dirs_exist_ok=True
    )

    name = get_random_name()

    # Create the requirements.txt if requirements are given
    if requirements is not None and isinstance(requirements, Sequence):
        # Get existing requirements and add the new ones
        if os.path.exists(os.path.join(tmpdir, 'requirements.txt')):
            with open(os.path.join(tmpdir, 'requirements.txt'), 'r') as f:
                requirements = set(requirements + tuple(f.read().splitlines()))

        with open(os.path.join(tmpdir, 'requirements.txt'), 'w') as f:
            f.write('\n'.join(requirements))

    # Remove langchain-serve itself from the requirements list as it may be entered by mistake and break things
    if os.path.exists(os.path.join(tmpdir, 'requirements.txt')):
        with open(os.path.join(tmpdir, 'requirements.txt'), 'r') as f:
            requirements = f.read().splitlines()

        requirements = [r for r in requirements if not r.startswith("langchain-serve")]

        with open(os.path.join(tmpdir, 'requirements.txt'), 'w') as f:
            f.write('\n'.join(requirements))

    # Create the Dockerfile
    with open(os.path.join(tmpdir, 'Dockerfile'), 'w') as f:
        dockerfile = [
            f'FROM jinawolf/serving-gateway:{version}',
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

    if platform:
        args.platform = platform

    if hubble_exists(name):
        args.force_update = name

    return HubIO(args).push().get('id'), _any_websocket_router(app)


@dataclass
class Defaults:
    instance: str = 'C3'
    autoscale_min: int = 0
    autoscale_max: int = 10
    autoscale_rps: int = 10
    autoscale_stable_window: int = DEFAULT_TIMEOUT
    autoscale_revision_timeout: int = DEFAULT_TIMEOUT

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
            self.autoscale_stable_window = config.get('autoscale', {}).get(
                'stable_window', self.autoscale_stable_window
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
                    'host': 'http://opentelemetry-collector.monitor.svc.cluster.local',
                    'port': 4317,
                },
            },
        }
    }


@dataclass
class AutoscaleConfig:
    min: int = Defaults.autoscale_min
    max: int = Defaults.autoscale_max
    rps: int = Defaults.autoscale_rps
    stable_window: int = Defaults.autoscale_stable_window
    revision_timeout: int = Defaults.autoscale_revision_timeout

    def to_dict(self) -> Dict:
        return {
            'autoscale': {
                'min': self.min,
                'max': self.max,
                'metric': 'rps',
                'target': self.rps,
                'stable_window': self.stable_window,
                'revision_timeout': self.revision_timeout,
            }
        }


@dataclass
class JCloudConfig:
    is_websocket: bool
    instance: str = Defaults.instance
    timeout: int = DEFAULT_TIMEOUT
    autoscale: AutoscaleConfig = field(init=False)

    def __post_init__(self):
        self.autoscale = AutoscaleConfig(
            stable_window=self.timeout, revision_timeout=self.timeout
        )

    def to_dict(self) -> Dict:
        return {
            'jcloud': {
                'expose': True,
                'resources': {
                    'instance': self.instance,
                    'capacity': 'spot',
                },
                'healthcheck': not self.is_websocket,
                'timeout': self.timeout,
                **self.autoscale.to_dict(),
            }
        }


def get_uvicorn_args() -> Dict:
    return {
        'uvicorn_kwargs': {
            'ws_ping_interval': None,
            'ws_ping_timeout': None,
        }
    }


def get_with_args_for_jcloud() -> Dict:
    return {
        'with': {
            'extra_search_paths': ['/workdir/lcserve'],
            **get_uvicorn_args(),
        }
    }


def get_jcloud_config(
    config_path: str = None, timeout: int = DEFAULT_TIMEOUT, is_websocket: bool = False
) -> JCloudConfig:
    jcloud_config = JCloudConfig(is_websocket=is_websocket, timeout=timeout)
    if not config_path:
        return jcloud_config

    with open(config_path, 'r') as f:
        config_data = yaml.safe_load(f)
        if not config_data:
            return jcloud_config

        instance = config_data.get('instance')
        autoscale_min = config_data.get('autoscale_min')

        if instance:
            jcloud_config.instance = instance
        if autoscale_min:
            jcloud_config.autoscale.min = autoscale_min

    return jcloud_config


def get_flow_dict(
    module: Union[str, List[str]],
    jcloud: bool = False,
    port: int = 8080,
    name: str = APP_NAME,
    timeout: int = DEFAULT_TIMEOUT,
    app_id: str = None,
    gateway_id: str = None,
    is_websocket: bool = False,
    jcloud_config_path: str = None,
) -> Dict:
    if isinstance(module, str):
        module = [module]

    if jcloud:
        jcloud_config = get_jcloud_config(
            config_path=jcloud_config_path, timeout=timeout, is_websocket=is_websocket
        )

    uses = get_gateway_uses(id=gateway_id) if jcloud else get_gateway_config_yaml_path()
    flow_dict = {
        'jtype': 'Flow',
        **(get_with_args_for_jcloud() if jcloud else {}),
        'gateway': {
            'uses': uses,
            'uses_with': {
                'modules': module,
            },
            'port': [port],
            'protocol': ['websocket'] if is_websocket else ['http'],
            **get_uvicorn_args(),
            **(jcloud_config.to_dict() if jcloud else {}),
        },
        **(get_global_jcloud_args(app_id=app_id, name=name) if jcloud else {}),
    }
    if os.environ.get("LCSERVE_TEST", False):
        flow_dict['with'] = {
            'metrics': True,
            'metrics_exporter_host': 'http://localhost',
            'metrics_exporter_port': 4317,
        }
    return flow_dict


def get_flow_yaml(
    module: Union[str, List[str]],
    jcloud: bool = False,
    port: int = 8080,
    name: str = APP_NAME,
    is_websocket: bool = False,
    jcloud_config_path: str = None,
) -> str:
    return yaml.safe_dump(
        get_flow_dict(
            module=module,
            port=port,
            name=name,
            is_websocket=is_websocket,
            jcloud=jcloud,
            jcloud_config_path=jcloud_config_path,
        ),
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
        flow_namespace = app_id.split("-")[-1]

        _add_row('App ID', app_id, bold_key=True, bold_value=True)
        _add_row('Phase', status.get('phase', ''))
        _add_row('Endpoint', endpoint)
        _add_row(
            'App logs',
            Markdown(APP_LOGS_URL.format(flow=flow_namespace), justify='center'),
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
