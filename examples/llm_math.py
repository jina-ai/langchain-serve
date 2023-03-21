# LLM Math chain
# Code taken from https://langchain.readthedocs.io/en/latest/modules/chains/examples/llm_math.html

import os

from langchain import LLMMathChain, OpenAI

os.environ['OPENAI_API_KEY'] = os.environ.get('OPENAI_API_KEY', 'sk-********')

llm = OpenAI(temperature=0)
# llm_math = LLMMathChain(llm=llm, verbose=True)
# llm_math.run("What is 13 raised to the .3432 power?")

import sys

# jina code starts here
from pydantic import Extra

sys.path.append('/home/deepankar/repos/langchain-serve')

from serve import ChainExecutor, CombinedMeta, Interact, ServeHTTP


class LLMMathChainExecutor(
    LLMMathChain, ChainExecutor, extra=Extra.allow, metaclass=CombinedMeta
):
    def __init__(self, *args, **kwargs):
        self.__init_parents__(LLMMathChain, *args, **kwargs)


with ServeHTTP(
    uses=LLMMathChainExecutor, uses_with={'llm': llm, 'verbose': True}
) as host:
    print(Interact(host, {'question': 'What is 13 raised to the .3432 power?'}))
