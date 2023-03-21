# Sequential chain.
# Code taken from https://langchain.readthedocs.io/en/latest/modules/chains/generic/sequential_chains.html#sequential-chain

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

import sys

# jina code starts here
from pydantic import Extra

sys.path.append('/home/deepankar/repos/langchain-serve')

from serve import ChainExecutor, CombinedMeta, Interact, ServeHTTP


class SequentialChainExecutor(
    SequentialChain, ChainExecutor, extra=Extra.allow, metaclass=CombinedMeta
):
    def __init__(self, *args, **kwargs):
        self.__init_parents__(SequentialChain, *args, **kwargs)


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
