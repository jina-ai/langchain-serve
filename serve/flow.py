from contextlib import contextmanager
from typing import Dict, Union

from docarray import Document, DocumentArray
from jina import Flow

from .helper import DEFAULT_KEY, RESULT, parse_uses_with


@contextmanager
def StartFlow(protocol, uses, uses_with, port=12345):
    with Flow(port=port, protocol=protocol).add(
        uses=uses,
        uses_with=parse_uses_with(uses_with),
        env={'JINA_LOG_LEVEL': 'INFO'},
    ) as f:
        yield str(f.protocol).lower() + '://' + f.host + ':' + str(f.port)


def ServeGRPC(uses, uses_with, port=12345):
    return StartFlow('grpc', uses, uses_with, port)


def ServeHTTP(uses, uses_with, port=12345):
    return StartFlow('http', uses, uses_with, port)


def ServeWebSocket(uses, uses_with, port=12345):
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
