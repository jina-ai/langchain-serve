import os
import sys

from langchain import LLMChain, OpenAI, PromptTemplate
from pydantic import Extra

sys.path.append('/home/deepankar/repos/langchain-serve')

from serve import ChainExecutor, CombinedMeta, Interact, ServeHTTP

os.environ['OPENAI_API_KEY'] = os.environ.get('OPENAI_API_KEY', 'sk-********')


class LLMChainExecutor(
    LLMChain, ChainExecutor, extra=Extra.allow, metaclass=CombinedMeta
):
    def __init__(self, *args, **kwargs):
        self.__init_parents__(LLMChain, *args, **kwargs)


with ServeHTTP(
    uses=LLMChainExecutor,
    uses_with={
        'llm': OpenAI(model_name='ada'),
        'prompt': PromptTemplate(
            input_variables=["product"],
            template="What is a good name for a company that makes {product}?",
        ),
    },
) as host:
    print(Interact(host, {'product': 'toothbrush'}))
