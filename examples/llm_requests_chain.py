import os

from langchain.chains import LLMChain, LLMRequestsChain
from langchain.llms import OpenAI
from langchain.prompts import PromptTemplate

os.environ['OPENAI_API_KEY'] = os.environ.get('OPENAI_API_KEY', 'sk-********')


template = """Between >>> and <<< are the raw search result text from google.
Extract the answer to the question '{query}' or say "not found" if the information is not contained.
Use the format
Extracted:<answer or "not found">
>>> {requests_result} <<<
Extracted:"""

PROMPT = PromptTemplate(
    input_variables=["query", "requests_result"],
    template=template,
)

# chain = LLMRequestsChain(llm_chain = LLMChain(llm=OpenAI(temperature=0), prompt=PROMPT))

question = "What are the Three (3) biggest countries, and their respective sizes?"
inputs = {
    "query": question,
    "url": "https://www.google.com/search?q=" + question.replace(" ", "+")
}

import sys

# jina code starts here
from pydantic import Extra

sys.path.append('/home/deepankar/repos/langchain-serve')

from serve import ChainExecutor, CombinedMeta, Interact, ServeHTTP

llm = OpenAI(model_name='ada', temperature=.7)


class LLMRequestsChainExecutor(LLMRequestsChain, ChainExecutor, extra=Extra.allow, metaclass=CombinedMeta):
    def __init__(self, *args, **kwargs):
        self.__init_parents__(LLMRequestsChain, *args, **kwargs)


with ServeHTTP(uses=LLMRequestsChainExecutor, uses_with={'llm_chain': LLMChain(llm=llm, prompt=PROMPT)}) as host:
    print(Interact(host, inputs))
    