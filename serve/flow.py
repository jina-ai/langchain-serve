from contextlib import contextmanager
from typing import Dict, Union, Tuple

from docarray import Document, DocumentArray
from jina import Flow

from .helper import AGENT_OUTPUT, DEFAULT_KEY, RESULT, parse_uses_with


@contextmanager
def StartFlow(protocol, uses, uses_with: Dict = None, port=12345):
    with Flow(port=port, protocol=protocol).add(
        uses=uses,
        uses_with=parse_uses_with(uses_with) if uses_with else None,
        env={'JINA_LOG_LEVEL': 'INFO'},
        allow_concurrent=True,
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
