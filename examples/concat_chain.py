# Custom chain.
# Code taken from https://langchain.readthedocs.io/en/latest/modules/chains/getting_started.html#create-a-custom-chain-with-the-chain-class

import os
from typing import Any, Dict, List

from langchain import LLMChain, OpenAI, PromptTemplate
from langchain.chains.base import Chain

os.environ['OPENAI_API_KEY'] = os.environ.get('OPENAI_API_KEY', 'sk-********')


class ConcatenateChain(Chain):
    chain_1: LLMChain
    chain_2: LLMChain

    @property
    def input_keys(self) -> List[str]:
        # Union of the input keys of the two chains.
        all_input_vars = set(self.chain_1.input_keys).union(
            set(self.chain_2.input_keys)
        )
        return list(all_input_vars)

    @property
    def output_keys(self) -> List[str]:
        return ['concat_output']

    def _call(self, inputs: Dict[str, str]) -> Dict[str, str]:
        output_1 = self.chain_1.run(inputs)
        output_2 = self.chain_2.run(inputs)
        return {'concat_output': output_1 + output_2}


llm = OpenAI(
    openai_api_key=os.environ['OPENAI_API_KEY'], model_name='ada', temperature=0.7
)
prompt_1 = PromptTemplate(
    input_variables=["product"],
    template="What is a good name for a company that makes {product}?",
)
chain_1 = LLMChain(llm=llm, prompt=prompt_1)

prompt_2 = PromptTemplate(
    input_variables=["product"],
    template="What is a good slogan for a company that makes {product}?",
)
chain_2 = LLMChain(llm=llm, prompt=prompt_2)

import sys

# jina code starts here
from pydantic import Extra

sys.path.append('/home/deepankar/repos/jcloud/play/llmexpt')

from serve import ChainExecutor, CombinedMeta, Interact, ServeHTTP


class ConcatenateChainExecutor(
    ConcatenateChain, ChainExecutor, extra=Extra.allow, metaclass=CombinedMeta
):
    def __init__(self, *args, **kwargs):
        self.__init_parents__(ConcatenateChain, *args, **kwargs)


with ServeHTTP(
    uses=ConcatenateChainExecutor, uses_with={'chain_1': chain_1, 'chain_2': chain_2}
) as host:
    print(Interact(host, {'product': 'toothbrush'}))
