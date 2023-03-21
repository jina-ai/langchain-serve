import os
from typing import Dict

from langchain import OpenAI, PromptTemplate
from langchain.chains import LLMChain, LLMRequestsChain, SequentialChain
from langchain.prompts import PromptTemplate

os.environ["OPENAI_API_KEY"] = "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"


class RequestsChain(LLMRequestsChain):
    """Chain that hits a URL and then uses an LLM to parse results."""

    llm_chain: LLMChain = None
    requests_key: str = None

    def _call(self, inputs: Dict[str, str]) -> Dict[str, str]:
        from bs4 import BeautifulSoup

        url = inputs[self.input_key]
        res = self.requests_wrapper.get(url)
        # extract the text from the html
        soup = BeautifulSoup(res, "html.parser")
        return {self.output_key: soup.get_text()[: self.text_length]}


requests_chain = RequestsChain(
    input_key='url',
    output_key='output',
)

search_template = """Between >>> and <<< are the raw search result text from google search html page.
Extract the answer to the question '{query}'. Please cleanup the answer to remove any extra text unrelated to the answer. 

Use the format
Extracted: answer
>>> {output} <<<
Extracted:"""

llm = OpenAI()
PROMPT = PromptTemplate(
    input_variables=["query", "output"],
    template=search_template,
)

llm_chain = LLMChain(
    llm=llm,
    prompt=PROMPT,
    output_key='text',
)


sequential_chain = SequentialChain(
    chains=[requests_chain, llm_chain],
    input_variables=["query", "url"],
    output_variables=["text"],
    verbose=True,
)
question = "IPL matches scheduled for Royal Challengers Bangalore in April"
# print(
#     sequential_chain.run(
#         {
#             "query": question,
#             "url": "https://www.google.com/search?q=" + question.replace(" ", "+"),
#         }
#     )
# )

import sys

sys.path.append('/home/deepankar/repos/langchain-serve')

from pydantic import Extra

from serve import ChainExecutor, CombinedMeta, Interact
from serve.helper import parse_uses_with


class LLMChainExecutor(
    LLMChain, ChainExecutor, extra=Extra.allow, metaclass=CombinedMeta
):
    def __init__(self, *args, **kwargs):
        self.__init_parents__(LLMChain, *args, **kwargs)


class RequestsChainExecutor(
    RequestsChain, ChainExecutor, extra=Extra.allow, metaclass=CombinedMeta
):
    def __init__(self, *args, **kwargs):
        self.__init_parents__(RequestsChain, *args, **kwargs)


from jina import Flow

output_key = 'text'
f = (
    Flow(port=12345, protocol='http')
    .add(
        name='requests',
        uses=RequestsChainExecutor,
        uses_with=parse_uses_with(
            {
                'input_key': 'url',
                'output_key': 'output',
            }
        ),
    )
    .add(
        name='llm',
        uses=LLMChainExecutor,
        uses_with=parse_uses_with(
            {
                'llm': OpenAI(),
                'prompt': PromptTemplate(
                    input_variables=["query", "output"],
                    template=search_template,
                ),
                'output_key': output_key,
            }
        ),
    )
)

with f:
    r = Interact(
        'http://0.0.0.0:12345',
        {
            'query': question,
            'url': "https://www.google.com/search?q=" + question.replace(" ", "+"),
        },
    )
    for d in r[0].docs:
        print(d.tags[output_key])
