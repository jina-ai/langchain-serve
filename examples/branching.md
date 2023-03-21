# Branching Chains in different Executors

## Goal 

This example creates 2 parallel `RequestChain`s that are executed in different Executors. The `RequestsChain` is responsible for making a request to a URL and extracting the text from the response. The `LLMChain` is responsible for merging the previous requests and running it through an LLM to get the answer. Following demo gets all the cricket matches scheduled for Royal Challengers Bangalore & Mumbai Indians in April.

## Creating Chains

```python

import os
from typing import Dict

from langchain import OpenAI, PromptTemplate
from langchain.chains import LLMChain, LLMRequestsChain
from langchain.prompts import PromptTemplate

os.environ["OPENAI_API_KEY"] = os.environ.get("OPENAI_API_KEY", "sk-********")

search_template = """Between >>> and <<< are the raw search result text from google search html page.
Extract the answer to the questions '{query1}' & '{query2}'. 
Please cleanup the answer to remove any extra text unrelated to the answer. 

>>> {output1} <<<
>>> {output2} <<<
"""


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
```

## Creating Executors

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
        name='requests1',
        uses=RequestsChainExecutor,
        uses_with=parse_uses_with(
            {
                'input_key': 'url1',
                'output_key': 'output1',
            }
        ),
        needs='gateway',
    )
    .add(
        name='requests2',
        uses=RequestsChainExecutor,
        uses_with=parse_uses_with(
            {
                'input_key': 'url2',
                'output_key': 'output2',
            }
        ),
        needs='gateway',
    )
    .add(
        name='llm',
        uses=LLMChainExecutor,
        uses_with=parse_uses_with(
            {
                'llm': OpenAI(),
                'prompt': PromptTemplate(
                    input_variables=["query1", "query2", "output1", "output2"],
                    template=search_template,
                ),
                'output_key': output_key,
            }
        ),
        needs=['requests1', 'requests2'],
        no_reduce=True,
    )
)


rcb_query = "IPL matches scheduled for Royal Challengers Bangalore in April 2023"
mi_query = "IPL matches scheduled for Mumbai Indians in April 2023"


search = lambda x: "https://www.google.com/search?q=" + x.replace(" ", "+")

with f:
    r = Interact(
        'http://0.0.0.0:12345',
        {
            'query1': rcb_query,
            'url1': search(rcb_query),
            'query2': mi_query,
            'url2': search(mi_query),
        },
    )
    for d in r[0].docs:
        print(d.tags[output_key])
```


```text
─────────────────────────────────────── 🎉 Flow is ready to serve! ───────────────────────────────────────
╭──────────────────────── 🔗 Endpoint ────────────────────────╮
│  ⛓   Protocol                                        HTTP  │
│  🏠     Local                                0.0.0.0:12345  │
│  🔒   Private                         192.168.29.185:12345  │
│  🌍    Public  2405:201:d007:e8e7:f7b4:eb77:2842:53f:12345  │
╰─────────────────────────────────────────────────────────────╯
╭─────────── 💎 HTTP extension ────────────╮
│  💬          Swagger UI        .../docs  │
│  📚               Redoc       .../redoc  │
╰──────────────────────────────────────────╯

Answer:
Royal Challengers Bangalore: Sun, 2 Apr, 7:30 pm RCB vs MI; Tue, 6 Apr, 7:30 pm KKR vs RCB; Mon, 10 Apr, 7:30 pm RCB vs LSG

Mumbai Indians: Sun, 2 Apr, 7:30 pm RCB vs MI; Sat, 8 Apr, 7:30 pm MI vs CSK; Fri, 11 Apr, 7:30 pm DC vs MI

```
