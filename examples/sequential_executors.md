# Sequential Chains in different Executors

## Goal

Langchain already implements a `SequentialChain` that can be used to chain multiple `Chains` together. But that happens in one process, which are tied to each other. This example shows how to use expand `SequentialChain` to work with >1 Executors. This is useful when we want to scale the `Chains` independently.

This example divides `SequentialChain` into 2 Executors: `RequestsChain` and `LLMChain`. The `RequestsChain` is responsible for making a request to a URL and extracting the text from the response. The `LLMChain` is responsible for taking the text and running it through an LLM to get the answer. Following demo gets all the cricket matches scheduled for Royal Challengers Bangalore in April.

## Running locally

```python
import os
from typing import Dict

from langchain import OpenAI, PromptTemplate
from langchain.chains import LLMChain, LLMRequestsChain, SequentialChain
from langchain.prompts import PromptTemplate

os.environ['OPENAI_API_KEY'] = os.environ.get('OPENAI_API_KEY', 'sk-********')


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
sequential_chain.run(
    {
        "query": question,
        "url": "https://www.google.com/search?q=" + question.replace(" ", "+"),
    }
)
```

## Create Executors from Chains

```python
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
```

## Serve HTTP Endpoint & Interact

```python

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
```

```text

─────────────────────────────────────── 🎉 Flow is ready to serve! ───────────────────────────────────────
╭──────────────────────── 🔗 Endpoint ────────────────────────╮
│  ⛓   Protocol                                         HTTP  │
│  🏠     Local                                0.0.0.0:12345  │
│  🔒   Private                         192.168.29.185:12345  │
│  🌍    Public  2405:201:d007:e8e7:f7b4:eb77:2842:53f:12345  │
╰─────────────────────────────────────────────────────────────╯
╭─────────── 💎 HTTP extension ────────────╮
│  💬          Swagger UI        .../docs  │
│  📚               Redoc       .../redoc  │
╰──────────────────────────────────────────╯

 Sun, 2 Apr, 7:30 pm RCB vs MI; 6 Apr, 7:30 pm KKR vs RCB; 10 Apr, 7:30 pm RCB vs LSG; 20 Apr, 3:30 pm PBKS vs RCB; 23 Apr, 3:30 pm RCB vs RR.

```
