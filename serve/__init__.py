from collections import defaultdict
from contextlib import contextmanager
from typing import Any, Dict, List, Union

from jina import Executor, Flow, requests
from langchain.chains.base import Chain
from langchain.chains.loading import load_chain_from_config
from pydantic import BaseModel

CLS = 'cls'
RESULT = 'result'
JINA_RESULTS = '__results__'
LLM_TYPE = '_type'
DEFAULT_FIELD = 'chain'


class CombinedMeta(type(Executor), type(BaseModel)):
    def __new__(cls, name, bases, namespace, **kwargs):
        namespace['__fields_set__'] = set()
        return super().__new__(cls, name, bases, namespace, **kwargs)


def base_model_kwargs(executor_kwargs: Dict, fields: Dict) -> Dict:
    _base_model_kwargs = {}

    def _parse(v):
        # TODO: dynamically load classes
        from langchain.llms import OpenAI
        from langchain.prompts import PromptTemplate

        if isinstance(v, dict):
            cls_str = v.get(CLS)
            if cls_str:
                try:
                    return load_chain_from_config(v['kwargs'])
                except Exception as e:
                    cls = locals()[cls_str]
                    allowed = {field.alias for field in cls.__fields__.values()}
                    _model_kwargs = v.get('kwargs', {})
                    for kk in _model_kwargs.copy().keys():
                        if kk not in allowed:
                            del _model_kwargs[kk]
                    return cls(**_model_kwargs)
            else:
                return {kk: _parse(vv) for kk, vv in v.items()}
        elif isinstance(v, list):
            return [_parse(vv) for vv in v]
        else:
            return v

    try:
        # remove jina specific kwargs by looking at the fields
        _executor_kwargs = {
            k: v for k, v in executor_kwargs.items() if k in fields or k == LLM_TYPE
        }
        _base_model_kwargs = load_chain_from_config(_executor_kwargs)
    except Exception as e:
        for _field, _kwargs in executor_kwargs.items():
            if _field in fields or _field in (CLS, 'kwargs', LLM_TYPE, DEFAULT_FIELD):
                try:
                    _base_model_kwargs[_field] = load_chain_from_config(_kwargs)
                except Exception as e:
                    _base_model_kwargs[_field] = _parse(_kwargs)

    return _base_model_kwargs


class ChainExecutor(Executor):
    def __init_parents__(self, chain_cls, *args, **kwargs):
        chain_cls.__init__(
            self, *args, **base_model_kwargs(kwargs, chain_cls.__fields__)
        )
        super().__init__(*args, **kwargs)

    @requests(on='/run')
    def __run_endpoint(self, parameters: Dict[str, Any], **kwargs) -> Dict[str, str]:
        if len(self.output_keys) == 1:
            return {RESULT: self.run(parameters)}
        else:
            return {RESULT: self(parameters)}

    @requests(on='/arun')
    async def __arun_endpoint(
        self, parameters: Dict[str, Any], **kwargs
    ) -> Dict[str, str]:
        if len(self.output_keys) == 1:
            return {RESULT: await self.arun(parameters)}
        else:
            return {RESULT: await self(parameters)}


def init_executor(self, chain_cls, *args, **kwargs):
    chain_cls.__init__(self, *args, **base_model_kwargs(kwargs, chain_cls.__fields__))
    ChainExecutor.__init__(self, *args, **kwargs)


def parse_uses_with(uses_with: Union[Dict, BaseModel, List]) -> Dict[str, Any]:
    _uses_with = defaultdict(dict)

    def _parse(v):
        if isinstance(v, BaseModel):
            return {'cls': v.__class__.__name__, 'kwargs': v.dict(skip_defaults=True)}
        elif isinstance(v, type):
            return {'cls': v.__name__}
        elif isinstance(v, dict):
            return (
                {'cls': v['cls'], 'kwargs': v['kwargs']}
                if 'cls' in v
                else {kk: _parse(vv) for kk, vv in v.items()}
            )
        elif isinstance(v, list):
            return [_parse(vv) for vv in v]
        elif isinstance(v, (str, bool)):
            return v
        elif v is None:
            return v
        else:
            return v

    if isinstance(uses_with, BaseModel):
        uses_with = uses_with.dict()

    if isinstance(uses_with, dict):
        print(f'uses_with: {uses_with}')
        for k, v in uses_with.items():
            _uses_with[k] = _parse(v)
    elif isinstance(uses_with, list):
        for v in uses_with:
            _uses_with.update(_parse(v))

    return _uses_with


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


def Interact(host, inputs):
    from jina import Client

    r = Client(host=host).post(on='/run', parameters=inputs, return_responses=True)
    if r:
        results = r[0].parameters.get(JINA_RESULTS, None)
        if results:
            # TODO: handle replicas
            for v in results.values():
                if RESULT in v:
                    return v[RESULT]
    return None


# print(
#     _parse_uses_with(
#         {
#             'chain_1': {
#                 'llm': OpenAI(),
#                 'prompt': PromptTemplate(
#                     input_variables=["product"],
#                     template="What is a good name for a company that makes {product}?",
#                 ),
#             },
#             'chain_2': {
#                 'llm': OpenAI(),
#                 'prompt': PromptTemplate(
#                     input_variables=["product"],
#                     template="What is a good slogan for a company that makes {product}?",
#                 ),
#             },
#         }
#     )
# )

# print(
#     parse_uses_with(
#         {
#             'chain_1': chain_1,
#             'chain_2': chain_2,
#         }
#     )
# )

# print(
#     _parse_uses_with(
#         {
#             'llm': OpenAI(),
#             'prompt': PromptTemplate(
#                 input_variables=["product"],
#                 template="What is a good name for a company that makes {product}?",
#             ),
#         }
#     )
# )
