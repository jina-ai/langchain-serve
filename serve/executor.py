from typing import Any, Dict

from jina import Executor, requests
from langchain.chains.loading import load_chain_from_config
from pydantic import BaseModel

from .helper import CLS, DEFAULT_FIELD, LLM_TYPE, RESULT


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
