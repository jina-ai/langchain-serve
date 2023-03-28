import os
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Dict, List, Tuple, Union

import yaml
from docarray import Document, DocumentArray
from jcloud.flow import CloudFlow
from jina import Flow

from .backend.gateway import PlaygroundGateway
from .backend.playground.utils.helper import (
    AGENT_OUTPUT,
    DEFAULT_KEY,
    RESULT,
    parse_uses_with,
)

ServingGatewayConfigFile = 'servinggateway_config.yml'
JCloudConfigFile = 'jcloud_config.yml'


@contextmanager
def StartFlow(protocol, uses, uses_with: Dict = None, port=12345):
    with Flow(port=port, protocol=protocol).add(
        uses=uses,
        uses_with=parse_uses_with(uses_with) if uses_with else None,
        env={'JINA_LOG_LEVEL': 'INFO'},
        allow_concurrent=True,
    ) as f:
        yield str(f.protocol).lower() + '://' + f.host + ':' + str(f.port)


@contextmanager
def StartFlowWithPlayground(protocol, uses, uses_with: Dict = None, port=12345):
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


@dataclass
class Defaults:
    instance: str = 'C2'
    autoscale_min: int = 1
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


def gateway_config_yaml_path() -> str:
    return os.path.join(os.path.dirname(__file__), ServingGatewayConfigFile)


def gateway_docker_image() -> str:
    return 'docker://jinawolf/12345-gateway:latest'


def get_global_jcloud_args() -> Dict:
    return {
        'jcloud': {
            'label': {
                'app': 'langchain',
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
            'extra_search_paths': '/workdir/lcserve',
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


def get_dummy_executor_args() -> Dict:
    # Because jcloud doesn't support deploying Flows without Executors
    return {
        'executors': [
            {
                'uses': 'jinahub+docker://Sentencizer',
                'name': 'sentencizer',
                'jcloud': {
                    'expose': False,
                    'resources': {
                        'capacity': 'spot',
                    },
                    'autoscale': {
                        'min': 0,
                        'max': 1,
                    },
                },
            }
        ]
    }


def get_flow_dict(
    mods: Union[str, List[str]],
    jcloud: bool = False,
    port: int = 12345,
) -> Dict:
    if isinstance(mods, str):
        mods = [mods]

    flow_dict = {
        'jtype': 'Flow',
        **(get_with_args_for_jcloud() if jcloud else {}),
        'gateway': {
            'uses': gateway_docker_image() if jcloud else gateway_config_yaml_path(),
            'uses_with': {
                'modules': mods,
            },
            'port': [port],
            'protocol': ['http'],
            **(get_gateway_jcloud_args() if jcloud else {}),
        },
        **(get_global_jcloud_args() if jcloud else {}),
        **(get_dummy_executor_args() if jcloud else {}),
    }
    return flow_dict


def get_flow_yaml(
    mods: Union[str, List[str]],
    jcloud: bool = False,
    port: int = 12345,
) -> str:
    return yaml.safe_dump(get_flow_dict(mods, jcloud, port), sort_keys=False)


def serve_on_jcloud(flow_dict: Dict):
    with tempfile.TemporaryDirectory() as tmpdir:
        flow_path = os.path.join(tmpdir, 'flow.yml')
        with open(flow_path, 'w') as f:
            yaml.safe_dump(flow_dict, f, sort_keys=False)

        print(f'Flow YAML written to {os.path.join(tmpdir, "flow.yml")}')
        with open(flow_path, 'r') as f:
            print(f.read())

        flow = CloudFlow(path=flow_path).__enter__()
        print(f'Flow deployed with endpoint: {flow.endpoints}')
