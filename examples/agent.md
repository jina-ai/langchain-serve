# Agents

## Running locally

```python
from langchain.agents import initialize_agent, load_tools
from langchain.llms import OpenAI

llm = OpenAI(temperature=0)

tools = load_tools(["serpapi", "llm-math"], llm=llm)

agent = initialize_agent(tools, llm, agent="zero-shot-react-description", verbose=True)
agent.run(
    "Who is Leo DiCaprio's girlfriend? What is her current age raised to the 0.43 power?"
)
```

## Serve HTTP Endpoint & Interact

```python
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
```

```text
─────────────────────────────────────── 🎉 Flow is ready to serve! ───────────────────────────────────────
╭──────────────────────── 🔗 Endpoint ─────────────────────────╮
│  ⛓   Protocol                                          HTTP  │
│  🏠     Local                                 0.0.0.0:12345  │
│  🔒   Private                          192.168.29.185:12345  │
│  🌍    Public  2405:201:d007:e8e7:3e0b:f419:14c3:61c6:12345  │
╰──────────────────────────────────────────────────────────────╯
╭─────────── 💎 HTTP extension ────────────╮
│  💬          Swagger UI        .../docs  │
│  📚               Redoc       .../redoc  │
╰──────────────────────────────────────────╯


> Entering new AgentExecutor chain...
 I need to find out who Leo DiCaprio's girlfriend is and then calculate her age raised to the 0.43 power.
Action: Search
Action Input: "Leo DiCaprio girlfriend"
Observation: He went on to date Gisele Bündchen, Bar Refaeli, Blake Lively, Toni Garrn and Nina Agdal, among others, before finally settling down with current girlfriend Camila Morrone, who is 23 years his junior.
Thought: I need to calculate Camila Morrone's age raised to the 0.43 power.
Action: Calculator
Action Input: 23^0.43
Observation: Answer: 3.8507291225496925

Thought: I now know the final answer.
Final Answer: Camila Morrone is Leo DiCaprio's girlfriend and her current age raised to the 0.43 power is 3.8507291225496925.

> Finished chain.
Camila Morrone is Leo DiCaprio's girlfriend and her current age raised to the 0.43 power is 3.8507291225496925.
```