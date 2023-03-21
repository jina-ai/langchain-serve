# Simple Sequential Chain

[Langchain Simple Sequential Chain](https://langchain.readthedocs.io/en/latest/modules/chains/generic/sequential_chains.html#simplesequentialchain)

## Running locally

```python
import os

from langchain.chains import LLMChain
from langchain.llms import OpenAI
from langchain.prompts import PromptTemplate

os.environ['OPENAI_API_KEY'] = os.environ.get('OPENAI_API_KEY', 'sk-********')


# This is an LLMChain to write a synopsis given a title of a play.
llm = OpenAI(temperature=0.7)
synopsis_template = """You are a playwright. Given the title of play, it is your job to write a synopsis for that title.

Title: {title}
Playwright: This is a synopsis for the above play:"""
synopsis_prompt_template = PromptTemplate(
    input_variables=["title"], template=synopsis_template
)
synopsis_chain = LLMChain(llm=llm, prompt=synopsis_prompt_template)

# This is an LLMChain to write a review of a play given a synopsis.
review_template = """You are a play critic from the New York Times. Given the synopsis of play, it is your job to write a review for that play.

Play Synopsis:
{synopsis}
Review from a New York Times play critic of the above play:"""
review_prompt_template = PromptTemplate(
    input_variables=["synopsis"], template=review_template
)
review_chain = LLMChain(llm=llm, prompt=review_prompt_template)


from langchain.chains import SimpleSequentialChain

overall_chain = SimpleSequentialChain(
    chains=[synopsis_chain, review_chain], verbose=True
)
review = overall_chain.run("Tragedy at sunset on the beach")

```

## Create Executor from Chain

```python
import sys
sys.path.append('/home/deepankar/repos/langchain-serve')

from pydantic import Extra
from serve import ChainExecutor, CombinedMeta, Interact, ServeHTTP


class SimpleSequentialChainExecutor(
    SimpleSequentialChain, ChainExecutor, extra=Extra.allow, metaclass=CombinedMeta
):
    def __init__(self, *args, **kwargs):
        self.__init_parents__(SimpleSequentialChain, *args, **kwargs)

```

## Serve HTTP Endpoint & Interact

```python
with ServeHTTP(
    uses=SimpleSequentialChainExecutor,
    uses_with={'chains': [synopsis_chain, review_chain]},
) as host:
    print(Interact(host, {'input': 'toothbrush'}))
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

"I was so thrilled at the fact that the play was a Broadway hit. It's been so long since I've seen a play so well done. I don't know if the cast is better or worse, but it still plays wonderfully. I especially loved the scene where two of the players are playing backgammon. I thought that was a nice touch. The only thing I think could have been improved on was the ending. It's so good that they are just being silly, which I'm sure they are, but it felt a bit forced to me. In fact, I'm still not sure what they do when they're being silly. It's a shame, because it was really well done, but I don't know if I would have liked it if it had been cut."
```