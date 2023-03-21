# LLM Requests Chain

[Langchain LLM Requests](https://langchain.readthedocs.io/en/latest/modules/chains/examples/llm_requests.html)

## Running locally

```python
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

llm = OpenAI(temperature=0)
PROMPT = PromptTemplate(
    input_variables=["query", "requests_result"],
    template=template,
)

chain = LLMRequestsChain(llm_chain = LLMChain(llm=llm, prompt=PROMPT))
question = "What are the Three (3) biggest countries, and their respective sizes?"
inputs = {
    "query": question,
    "url": "https://www.google.com/search?q=" + question.replace(" ", "+")
}
chain(inputs)
```


## Create Executor from Chain

```python
import sys

sys.path.append('/home/deepankar/repos/langchain-serve')

from pydantic import Extra
from serve import ChainExecutor, CombinedMeta

class LLMRequestsChainExecutor(LLMRequestsChain, ChainExecutor, extra=Extra.allow, metaclass=CombinedMeta):
    def __init__(self, *args, **kwargs):
        self.__init_parents__(LLMRequestsChain, *args, **kwargs)
```

## Serve HTTP Endpoint & Interact

```python
from serve import Interact, ServeHTTP

with ServeHTTP(uses=LLMRequestsChainExecutor, uses_with={'llm_chain': LLMChain(llm=llm, prompt=PROMPT)}) as host:
    print(Interact(host, inputs))
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

<answer or "not found">
>>> What are the 3 biggest countries, and their respective sizes? - Google SearchGoogle ×Please click here if you are not redirected within a few seconds.    AllImagesBooksNews Maps Videos Shopping Search tools    AllImagesBooksNews Maps Videos Shopping Search tools    AnytimeAny timePast hourPast 24 hoursPast weekPast monthPast yearAll resultsAll resultsVerbatimThe Largest and the Smallest Countries in the World by Areawww.nationsonline.org › oneworld › countries_by_areaThe three largest sovereign countries by surface area are Russia, Canada, and the United States.
(2010 census population 143,085)
```

[Read more about serving endpoint with other protocols](protocols.md).