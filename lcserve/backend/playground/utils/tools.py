import inspect
import os
import re
from typing import List

import pydantic
from langchain.agents.load_tools import (
    _BASE_TOOLS,
    _EXTRA_LLM_TOOLS,
    _EXTRA_OPTIONAL_TOOLS,
    _LLM_TOOLS,
)
from langchain.llms import OpenAI
from pydantic import BaseModel, Field

_all_tools = {**_BASE_TOOLS, **_EXTRA_LLM_TOOLS, **_EXTRA_OPTIONAL_TOOLS, **_LLM_TOOLS}


def get_dummy_token():
    return 'dummy_token'


def get_dummy_llm():
    os.environ['OPENAI_API_KEY'] = get_dummy_token()
    return OpenAI(temperature=0)


def missing_key_from_err(error):
    validation_err_pattern = r"\`([a-zA-Z0-9_]+)\`"
    matches = re.findall(validation_err_pattern, error)
    return [m for m in matches if all(c.islower() or c == '_' for c in m)]


class LangchainTool(BaseModel):
    name: str
    api: str
    args: List[str] = Field(default_factory=list)


def get_all_langchain_tools() -> List[LangchainTool]:
    l_tools = []
    for k, v in _all_tools.items():
        args = []
        if isinstance(v, tuple):
            func = v[0]
            keys = v[1:][0]
        else:
            func = v
            keys = []

        sig = inspect.signature(func)
        if len(sig.parameters) == 0:
            name = func().name
        elif 'llm' in sig.parameters:
            try:
                name = func(get_dummy_llm()).name
            except KeyError as e:
                missing_key = e.args[0]
                name = func(get_dummy_llm(), **{missing_key: get_dummy_token()}).name
                args = [missing_key]
        elif 'kwargs' in sig.parameters:
            try:
                name = func().name
            except pydantic.ValidationError as e:
                keys = missing_key_from_err(e.errors()[0]['msg'])
                try:
                    name = func(**{k: get_dummy_token() for k in keys}).name
                    args = keys
                except pydantic.ValidationError as e:
                    more_keys = missing_key_from_err(e.errors()[0]['msg'])
                    name = func(**{k: get_dummy_token() for k in keys + more_keys}).name
                    args = keys + more_keys

        l_tools.append(LangchainTool(name=name, api=k, args=args))

    return l_tools


ALL_TOOLS = {t.name: {'api': t.api, 'args': t.args} for t in get_all_langchain_tools()}
ALL_TOOL_NAMES = [t.name for t in get_all_langchain_tools()]

# https://python.langchain.com/en/latest/modules/agents/agents.html
ALL_AGENT_TYPES = {
    'MRKL': 'zero-shot-react-description',
    'ReAct': 'react-docstore',
    'Self-Ask-With-Search': 'self-ask-with-search',
}
