## LLM Match Chain

https://langchain.readthedocs.io/en/latest/modules/chains/examples/llm_math.html


### Running locally

```python
import os

from langchain import LLMMathChain, OpenAI

os.environ['OPENAI_API_KEY'] = os.environ.get('OPENAI_API_KEY', 'sk-********')

llm = OpenAI(temperature=0)
llm_math = LLMMathChain(llm=llm, verbose=True)
llm_math.run("What is 13 raised to the .3432 power?")
```

### Serve HTTP Endpoint

```python
import sys

sys.path.append('/home/deepankar/repos/langchain-serve')

from pydantic import Extra
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

> Entering new LLMMathChainExecutor chain...
What is 13 raised to the .3432 power?
```python
import math
print(math.pow(13, .3432))
```

Answer: 2.4116004626599237

> Finished chain.
Answer: 2.4116004626599237
```