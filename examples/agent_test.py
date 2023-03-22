from langchain.agents import initialize_agent, load_tools
from langchain.llms import OpenAI

llm = OpenAI(temperature=0)

tools = load_tools(["serpapi", "llm-math"], llm=llm)

agent = initialize_agent(tools, llm, agent="zero-shot-react-description", verbose=True)
# agent.run(
#     "Who is Leo DiCaprio's girlfriend? What is her current age raised to the 0.43 power?"
# )

import sys

sys.path.append('/home/deepankar/repos/langchain-serve')

from serve import Interact, JinaAgentExecutor, ServeHTTP

with ServeHTTP(
    uses=JinaAgentExecutor,
    uses_with={
        'tools': {
            'tool_names': ['serpapi', 'llm-math'],
            'llm': llm,
        },
        'llm': llm,
        'agent': "zero-shot-react-description",
        'verbose': True,
    },
) as host:
    print(
        Interact(
            host,
            "Who is Leo DiCaprio's girlfriend? What is her current age raised to the 0.43 power?",
        )
    )
