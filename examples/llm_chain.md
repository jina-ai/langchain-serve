# LLM Chain

[Langchain LLM Chain](https://langchain.readthedocs.io/en/latest/modules/chains/examples/llm_chain.html)

## Running locally

```python
from langchain.prompts import PromptTemplate
from langchain.llms import OpenAI

llm = OpenAI(temperature=0.9)
prompt = PromptTemplate(
    input_variables=["product"],
    template="What is a good name for a company that makes {product}?",
)

from langchain.chains import LLMChain
chain = LLMChain(llm=llm, prompt=prompt)

# Run the chain only specifying the input variable.
print(chain.run("colorful socks"))
```

## Create Executor from Chain

```python
import sys

sys.path.append('/home/deepankar/repos/langchain-serve')

from pydantic import Extra
from serve import ChainExecutor, CombinedMeta

class LLMChainExecutor(LLMChain, ChainExecutor, extra=Extra.allow, metaclass=CombinedMeta):
    def __init__(self, *args, **kwargs):
        self.__init_parents__(LLMChain, *args, **kwargs)
```


## Serve HTTP Endpoint & Interact

```python
from serve import Interact, ServeHTTP

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


A good name for a company that makes toothbrush is a good name for a company that makes toothbrush. There is no wrong answer. The name of the company that makes toothbrush is a good name for a company that makes toothbrush. The name of the company that makes toothbrush is a good name for a company that makes toothbrush. The name of the company that makes toothbrush is a good name for a company that makes toothbrush. The name of the company that makes toothbrush is a good name for a company that makes toothbrush. The name of the company that makes toothbrush is a good name for a company that makes toothbrush. The name of the company that makes toothbrush is a good name for a company that makes toothbrush. The name of the company that makes toothbrush is a good name for a company that makes toothbrush. The name of the company that makes toothbrush is a good name for a company that makes toothbrush. The name of the company that makes toothbrush is a good name for a company that makes toothbrush. The name of the company that makes toothbrush is a good name for a company that makes toothbrush. The name of the company that makes toothbrush is a good name for a company
```

[Read more about serving endpoint with other protocols](protocols.md).
