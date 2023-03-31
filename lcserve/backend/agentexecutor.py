import threading
from contextlib import nullcontext
from typing import Any, Dict, Optional, Union

from docarray import Document, DocumentArray
from jina import Executor, requests
from langchain.agents import AgentExecutor, initialize_agent, load_tools
from langchain.chains.loading import load_chain_from_config
from pydantic import BaseModel

from .playground.utils.helper import (
    AGENT_OUTPUT,
    CLS,
    DEFAULT_FIELD,
    DEFAULT_KEY,
    LLM_TYPE,
    RESULT,
    Capturing,
    EnvironmentVarCtxtManager,
)


class CombinedMeta(type(Executor), type(BaseModel)):
    def __new__(cls, name, bases, namespace, **kwargs):
        namespace['__fields_set__'] = set()
        return super().__new__(cls, name, bases, namespace, **kwargs)


def _chain_base_model_kwargs(executor_kwargs: Dict, fields: Dict = {}) -> Dict:
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
            if (fields and _field in fields) or _field in (
                CLS,
                'kwargs',
                LLM_TYPE,
                DEFAULT_FIELD,
            ):
                try:
                    _base_model_kwargs[_field] = load_chain_from_config(_kwargs)
                except Exception as e:
                    _base_model_kwargs[_field] = _parse(_kwargs)

    return _base_model_kwargs


def _agent_base_model_args(executor_kwargs: Dict) -> AgentExecutor:
    def _get_llm_obj(llm_dict: Dict):
        return _chain_base_model_kwargs({'llm': llm_dict}, {'llm': None})['llm']

    def _get_default_llm_obj():
        from langchain.llms import OpenAI

        return OpenAI()

    if 'tools' not in executor_kwargs or not isinstance(executor_kwargs['tools'], dict):
        raise ValueError('tools must be specified in the config')
    else:
        tools = executor_kwargs['tools']
        tools['llm'] = (
            _get_llm_obj(tools['llm']) if tools.get('llm') else _get_default_llm_obj()
        )
        tools = load_tools(**tools)
        executor_kwargs.pop('tools')

    if 'llm' not in executor_kwargs:
        llm = _get_default_llm_obj()
    else:
        llm = _get_llm_obj(executor_kwargs['llm'])
        executor_kwargs.pop('llm')

    if (
        'agent' in executor_kwargs
        and executor_kwargs['agent'] == 'self-ask-with-search'
    ):
        if len(tools) > 1:
            raise ValueError(
                'self-ask-with-search only works with one tool, but got %d' % len(tools)
            )
        if tools[0].name != 'Intermediate Answer':
            tools[0].name = 'Intermediate Answer'

    return initialize_agent(tools=tools, llm=llm, **executor_kwargs)


class ChainExecutor(Executor):
    def __init_parents__(self, chain_cls, *args, **kwargs):
        chain_cls.__init__(
            self, *args, **_chain_base_model_kwargs(kwargs, chain_cls.__fields__)
        )
        super().__init__(*args, **kwargs)

    def _handle_merge(self, docs_map: Dict[str, DocumentArray]) -> DocumentArray:
        # Merge Documnets with same ID into one Document and create the DocumentArray
        da = DocumentArray()
        for k, v in docs_map.items():
            for doc in v:
                if doc.id in da:
                    da[doc.id].tags.update(doc.tags)
                else:
                    da.append(doc)
        return da

    @requests(on='/run')
    def __run_endpoint(
        self,
        docs: DocumentArray,
        docs_map: Optional[Dict[str, DocumentArray]],
        **kwargs,
    ) -> DocumentArray:
        if len(docs_map) > 1:
            docs = self._handle_merge(docs_map)

        for doc in docs:
            self.logger.debug(f'calling run on {doc.tags.keys()}')
            if len(self.output_keys) == 1:
                _result = {self.output_keys[0]: self.run(doc.tags)}
            else:
                _result = {RESULT: self(doc.tags)}
            doc.tags.update(_result)
        return docs

    @requests(on='/arun')
    async def __arun_endpoint(
        self,
        docs: DocumentArray,
        docs_map: Optional[Dict[str, DocumentArray]],
        **kwargs,
    ) -> DocumentArray:
        if len(docs_map) > 1:
            docs = self._handle_merge(docs_map)

        for doc in docs:
            self.logger.debug(f'calling run on {doc.tags.keys()}')
            if len(self.output_keys) == 1:
                _result = {self.output_keys[0]: await self.arun(doc.tags)}
            else:
                _result = {RESULT: await self(doc.tags)}
            doc.tags.update(_result)
        return docs


class LangchainAgentExecutor(Executor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._capture_lock = threading.Lock()

    @staticmethod
    def run_input(doc: Document) -> Dict:
        return doc.tags if DEFAULT_KEY not in doc.tags else doc.tags[DEFAULT_KEY]

    def get_capture_ctx(self) -> Capturing:
        return (
            nullcontext()
            if self._capture_lock.locked()
            else Capturing(lock=self._capture_lock)
        )

    def update_agent_output(
        self,
        cap: Union[Capturing, nullcontext],
        doc: Document,
        html: bool = False,
    ):
        from ansi2html import Ansi2HTMLConverter

        if isinstance(cap, Capturing):
            if html:
                converter = Ansi2HTMLConverter()
                doc.tags.update({AGENT_OUTPUT: converter.convert(''.join(cap))})
            else:
                doc.tags.update({AGENT_OUTPUT: ''.join(cap)})
        else:
            doc.tags.update({AGENT_OUTPUT: ''})

    @requests(on='/load_and_run')
    def __load_and_run_endpoint(
        self, docs: DocumentArray, parameters, **kwargs
    ) -> DocumentArray:
        self.logger.info(f'loading agent with {parameters} and docs {docs}')
        with EnvironmentVarCtxtManager(
            parameters['env'] if 'env' in parameters else {}
        ):
            try:
                agent = _agent_base_model_args(parameters)
            except ValueError as e:
                self.logger.error(e)
                for doc in docs:
                    doc.tags.update({RESULT: str(e)})
                return docs

            html = parameters['html'] if 'html' in parameters else False
            for doc in docs:
                self.logger.debug(f'calling run on {doc.tags.keys()}')
                with self.get_capture_ctx() as cap:
                    doc.tags.update({RESULT: agent.run(self.run_input(doc))})
                self.update_agent_output(cap, doc, html)
        return docs

    @requests(on='/aload_and_run')
    async def __aload_and_run_endpoint(
        self, docs: DocumentArray, parameters, **kwargs
    ) -> DocumentArray:
        self.logger.info(f'loading agent with {parameters} and docs {docs}')
        with EnvironmentVarCtxtManager(
            parameters['env'] if 'env' in parameters else {}
        ):
            try:
                agent = _agent_base_model_args(parameters)
            except ValueError as e:
                self.logger.error(e)
                for doc in docs:
                    doc.tags.update({RESULT: str(e)})
                return docs

            html = parameters['html'] if 'html' in parameters else False
            for doc in docs:
                self.logger.debug(f'calling run on {doc.tags.keys()}')
                with self.get_capture_ctx() as cap:
                    doc.tags.update({RESULT: await agent.arun(self.run_input(doc))})
                self.update_agent_output(cap, doc, html)

        return docs
