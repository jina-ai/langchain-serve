# Sequential Chain

[Langchain Sequential Chain](https://langchain.readthedocs.io/en/latest/modules/chains/generic/sequential_chains.html#sequential-chain)

## Running locally

```python
import os

from langchain.chains import LLMChain
from langchain.llms import OpenAI
from langchain.prompts import PromptTemplate

os.environ['OPENAI_API_KEY'] = os.environ.get('OPENAI_API_KEY', 'sk-********')


# This is an LLMChain to write a synopsis given a title of a play and the era it is set in.
llm = OpenAI(model_name='ada', temperature=0.7)
template = """You are a playwright. Given the title of play and the era it is set in, it is your job to write a synopsis for that title.

Title: {title}
Era: {era}
Playwright: This is a synopsis for the above play:"""
prompt_template = PromptTemplate(input_variables=["title", 'era'], template=template)
synopsis_chain = LLMChain(llm=llm, prompt=prompt_template, output_key="synopsis")

# This is an LLMChain to write a review of a play given a synopsis.
llm = OpenAI(model_name='ada', temperature=0.7)
template = """You are a play critic from the New York Times. Given the synopsis of play, it is your job to write a review for that play.

Play Synopsis:
{synopsis}
Review from a New York Times play critic of the above play:"""
prompt_template = PromptTemplate(input_variables=["synopsis"], template=template)
review_chain = LLMChain(llm=llm, prompt=prompt_template, output_key="review")

# This is the overall chain where we run these two chains in sequence.
from langchain.chains import SequentialChain

overall_chain = SequentialChain(
    chains=[synopsis_chain, review_chain],
    input_variables=["era", "title"],
    # Here we return multiple variables
    output_variables=["synopsis", "review"],
    verbose=True,
)
overall_chain({"title":"Tragedy at sunset on the beach", "era": "Victorian England"})
```

## Create Executor from Chain

```python
import sys
sys.path.append('/home/deepankar/repos/langchain-serve')


from pydantic import Extra
from serve import ChainExecutor, CombinedMeta


class SequentialChainExecutor(
    SequentialChain, ChainExecutor, extra=Extra.allow, metaclass=CombinedMeta
):
    def __init__(self, *args, **kwargs):
        self.__init_parents__(SequentialChain, *args, **kwargs)
```

## Serve HTTP Endpoint & Interact

```python
from serve import Interact, ServeHTTP


with ServeHTTP(
    uses=SequentialChainExecutor,
    uses_with={
        'chains': [synopsis_chain, review_chain],
        'input_variables': ["era", "title"],
        'output_variables': ["synopsis", "review"],
    },
) as host:
    print(
        Interact(
            host,
            {"era": "Victorian England", "title": "Tragedy at sunset on the beach"},
        )
    )
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

{'review': '\n\n\nReview from a play critic of the above play:\n\n\nReview from a play critic of the above play:\n\n\nReview from a play critic of the above play:\n\n\nReview from a play critic of the above play:\n\n\nReview from a play critic of the above play:\n\n\nReview from a play critic of the above play:\n\n\nReview from a play critic of the above play:\n\n\nReview from a play critic of the above play:\n\n\nReview from a play critic of the above play:\n\n\n\n\n', 'synopsis': '\n\nThe play is set in Victorian England during the 1850s. For this particular play, I needed to use the above synopsis to describe the setting.\n\n"Name" is an abbreviation of "name", or "a name", which I decided to use as the name of the play in the synopsis.\n\n"Name" is used in the synopsis to describe the play, but it is also used in the play itself.\n\nFor example, in the above play I want to tell the audience what the play is about, but I also want to tell them what the play is called.\n\nAs I discussed in my introduction to this blog post, the only information I needed for the play\'s title was the name. I could have used the name to describe the play, but it would have been too generic. So I decided to use the name to describe the play.\n\nFor example, in the above play I want to tell the audience what the play is about, but I also want to tell them what the play is called.\n\nAs I discussed in my introduction to this blog post, the only information I needed for the play\'s title was the name. I could have used the name to describe the play, but it would', 'title': 'Tragedy at sunset on the beach', 'era': 'Victorian England'}
```