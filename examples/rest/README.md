# 🔄 REST APIs using `@serving` decorator

`langchain-serve` allows you to easily wrap your LangChain applications with REST APIs using the `@serving` decorator. This enables you to integrate your local LangChain applications with a variety of external applications seamlessly, broadening your application's reach and functionality.


This involves 4 simple steps. Let's start by taking a simple example that uses `ZeroShotAgent` with a `Search` tool to ask a question. 

```python
# app.py
from langchain.agents import ZeroShotAgent, Tool, AgentExecutor
from langchain import OpenAI, SerpAPIWrapper, LLMChain

search = SerpAPIWrapper()
tools = [
    Tool(
        name = "Search",
        func=search.run,
        description="useful for when you need to answer questions about current events"
    )
]

prefix = """Answer the following questions as best you can, but speaking as a pirate might speak. You have access to the following tools:"""
suffix = """Begin! Remember to speak as a pirate when giving your final answer. Use lots of "Args"

Question: {input}
{agent_scratchpad}"""

prompt = ZeroShotAgent.create_prompt(
    tools, 
    prefix=prefix, 
    suffix=suffix, 
    input_variables=["input", "agent_scratchpad"]
)

llm_chain = LLMChain(llm=OpenAI(temperature=0), prompt=prompt)
tool_names = [tool.name for tool in tools]
agent = ZeroShotAgent(llm_chain=llm_chain, allowed_tools=tool_names)
agent_executor = AgentExecutor.from_agent_and_tools(agent=agent, tools=tools, verbose=True)
agent_executor.run("How many people live in canada as of 2023?")
```

#### Output


```text
> Entering new AgentExecutor chain...
Thought: I need to find out the population of Canada
Action: Search
Action Input: Population of Canada 2023
Observation: The current population of Canada is 38,610,447 as of Saturday, February 18, 2023, based on Worldometer elaboration of the latest United Nations data. Canada 2020 population is estimated at 37,742,154 people at mid year according to UN data.
Thought: I now know the final answer
Final Answer: Arrr, Canada be havin' 38,610,447 scallywags livin' there as of 2023!

> Finished chain.
```

### Step 1: 

**Refactor your code to function(s) that should be served with `@serving` decorator.**


```python
# app.py
from langchain import LLMChain, OpenAI, SerpAPIWrapper
from langchain.agents import AgentExecutor, Tool, ZeroShotAgent

from lcserve import serving


@serving
def ask(input: str) -> str:
    search = SerpAPIWrapper()
    tools = [
        Tool(
            name="Search",
            func=search.run,
            description="useful for when you need to answer questions about current events",
        )
    ]
    prefix = """Answer the following questions as best you can, but speaking as a pirate might speak. You have access to the following tools:"""
    suffix = """Begin! Remember to speak as a pirate when giving your final answer. Use lots of "Args"

    Question: {input}
    {agent_scratchpad}"""

    prompt = ZeroShotAgent.create_prompt(
        tools,
        prefix=prefix,
        suffix=suffix,
        input_variables=["input", "agent_scratchpad"],
    )

    print(prompt.template)

    llm_chain = LLMChain(llm=OpenAI(temperature=0), prompt=prompt)
    tool_names = [tool.name for tool in tools]
    agent = ZeroShotAgent(llm_chain=llm_chain, allowed_tools=tool_names)

    agent_executor = AgentExecutor.from_agent_and_tools(
        agent=agent, tools=tools, verbose=True
    )

    return agent_executor.run(input)

if __name__ == "__main__":
    ask('How many people live in canada as of 2023?')
```

##### What changed?

- We moved our code to an `ask` function.
- Added type hints to the function parameters (input and output), so API definition can be generated.
- Imported `from lcserve import serving` and added `@serving` decorator to the `ask` function.
- Added `if __name__ == "__main__":` block to test the function locally.

---

### Step 2:

**Create a `requirements.txt` file in your app directory to ensure all necessary dependencies are installed.**

```text
# requirements.txt
openai
google-search-results
```
</>

### Step 3:

**Run `lc-serve deploy local app` to test your API locally.**

> `app` is the name of the module that contains the `ask` function.

```bash
lc-serve deploy local app
```

<details>
<summary>Show output</summary>

```text
────────────────────────────────────────────────────────────────────────────────────────────────────── 🎉 Flow is ready to serve! ───────────────────────────────────────────────────────────────────────────────────────────────────────
╭──────────────────────── 🔗 Endpoint ────────────────────────╮
│  ⛓   Protocol                                         HTTP  │
│  🏠     Local                                 0.0.0.0:8080  │
│  🔒   Private                          192.168.29.185:8080  │
│  🌍    Public  2405:201:d007:e8e7:2c33:cf8e:ed66:2018:8080  │
╰─────────────────────────────────────────────────────────────╯
╭─────────── 💎 HTTP extension ────────────╮
│  💬          Swagger UI        .../docs  │
│  📚               Redoc       .../redoc  │
╰──────────────────────────────────────────╯
```

</details>


Let's open the [Swagger UI](http://localhost:8080/docs) to test our API locally. With `Try it out` button, we can test our API with different inputs.


<details>
<summary>Show Swagger UI</summary>

![Local Swagger UI](../../.github/images/local-swagger-ui.png)

</details>

Let's test our local API with `How many people live in canada as of 2023?` input with a cURL command.

```bash
curl -X 'POST' \
  'http://localhost:8080/ask' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "input": "How many people live in canada as of 2023?",
  "envs": {
    "OPENAI_API_KEY": "'"${OPENAI_API_KEY}"'",
    "SERPAPI_API_KEY": "'"${SERPAPI_API_KEY}"'"
  }
}'
```

```json
{
  "result": "Arrr, there be 38,645,670 people livin' in Canada as of 2023!",
  "error": "",
  "stdout": "Answer the following questions as best you can, but speaking as a pirate might speak. You have access to the following tools:\n\nSearch: useful for when you need to answer questions about current events\n\nUse the following format:\n\nQuestion: the input question you must answer\nThought: you should always think about what to do\nAction: the action to take, should be one of [Search]\nAction Input: the input to the action\nObservation: the result of the action\n... (this Thought/Action/Action Input/Observation can repeat N times)\nThought: I now know the final answer\nFinal Answer: the final answer to the original input question\n\nBegin! Remember to speak as a pirate when giving your final answer. Use lots of \"Args\"\n\n    Question: {input}\n    {agent_scratchpad}\n\n\n\u001b[1m> Entering new AgentExecutor chain...\u001b[0m\n\u001b[32;1m\u001b[1;3m\nThought: I need to find out how many people live in Canada\nAction: Search\nAction Input: How many people live in Canada as of 2023\u001b[0m\nObservation: \u001b[36;1m\u001b[1;3mThe current population of Canada is 38,645,670 as of Wednesday, March 29, 2023, based on Worldometer elaboration of the latest United Nations data.\u001b[0m\nThought:\u001b[32;1m\u001b[1;3m I now know the final answer\nFinal Answer: Arrr, there be 38,645,670 people livin' in Canada as of 2023!\u001b[0m\n\n\u001b[1m> Finished chain.\u001b[0m"
}
```

##### What happened?

- `POST /ask` is generated from `ask` function defined in `app.py`.
- `input` is an argrment defined in `ask` function. 
- `envs` is a dictionary of environment variables that will be passed to all the functions decorated with `@serving` decorator.
- return type of `ask` function is `str`. So, `result` would carry the return value of `ask` function.
- If there is an error, `error` would carry the error message.
- `stdout` would carry the output of the function decorated with `@serving` decorator.


---

### Step 4:

**Run `lc-serve deploy jcloud app` to deploy your API to Jina AI Cloud.**

```bash
# Login to Jina AI Cloud
jina auth login

# Deploy your app to Jina AI Cloud
lc-serve deploy jcloud app
```

<details>
<summary>Show complete output</summary>

```text
⠇ Pushing `/tmp/tmp7kt5qqrn` ...🔐 You are logged in to Jina AI as ***. To log out, use jina auth logout.
╭────────────────────────── Published ───────────────────────────╮
│                                                                │
│   📛 Name           n-64a15                                    │
│   🔗 Jina Hub URL   https://cloud.jina.ai/executor/6p1zio87/   │
│   👀 Visibility     public                                     │
│                                                                │
╰────────────────────────────────────────────────────────────────╯
╭─────────────────────── 🎉 Flow is available! ───────────────────────╮
│                                                                     │
│   ID               langchain-ee4aef57d9                             │
│   Gateway (Http)   https://langchain-ee4aef57d9-http.wolf.jina.ai   │
│   Dashboard        https://dashboard.wolf.jina.ai/flow/ee4aef57d9   │
│                                                                     │
╰─────────────────────────────────────────────────────────────────────╯
```
</details>


```text
╭──────────────┬─────────────────────────────────────────────────────────────╮
│ AppID        │                    langchain-ee4aef57d9                     │
├──────────────┼─────────────────────────────────────────────────────────────┤
│ Phase        │                           Serving                           │
├──────────────┼─────────────────────────────────────────────────────────────┤
│ Endpoint     │       https://langchain-ee4aef57d9-http.wolf.jina.ai        │
├──────────────┼─────────────────────────────────────────────────────────────┤
│ Swagger UI   │     https://langchain-ee4aef57d9-http.wolf.jina.ai/docs     │
├──────────────┼─────────────────────────────────────────────────────────────┤
│ OpenAPI JSON │ https://langchain-ee4aef57d9-http.wolf.jina.ai/openapi.json │
╰──────────────┴─────────────────────────────────────────────────────────────╯
```

Let's open the Swagger UI to test our API on Jina AI Cloud. With `Try it out` button, we can test our API with different inputs.

<details>
<summary>Show Swagger UI</summary>

<p float="center">
  <img src="../../.github/images/jcloud-swagger-ui.png" width="400" />
  <img src="../../.github/images/jcloud-openapi.png" width="300" />
</p>

</details>


Let's test the API on JCloud with `How many people live in canada as of 2023?` input with a cURL command (Replace the Hostname with your own hostname):

```bash
curl -X 'POST' \
  'https://langchain-ee4aef57d9-http.wolf.jina.ai/ask' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "input": "How many people live in canada as of 2023?",
  "envs": {
    "OPENAI_API_KEY": "'"${OPENAI_API_KEY}"'",
    "SERPAPI_API_KEY": "'"${SERPAPI_API_KEY}"'"
  }
}'
```

```json
{
  "result": "Arrr, there be 38,645,670 people livin' in Canada as of 2023!",
  "error": "",
  "stdout": "Answer the following questions as best you can, but speaking as a pirate might speak. You have access to the following tools:\n\nSearch: useful for when you need to answer questions about current events\n\nUse the following format:\n\nQuestion: the input question you must answer\nThought: you should always think about what to do\nAction: the action to take, should be one of [Search]\nAction Input: the input to the action\nObservation: the result of the action\n... (this Thought/Action/Action Input/Observation can repeat N times)\nThought: I now know the final answer\nFinal Answer: the final answer to the original input question\n\nBegin! Remember to speak as a pirate when giving your final answer. Use lots of \"Args\"\n\n    Question: {input}\n    {agent_scratchpad}\n\n\n\u001b[1m> Entering new AgentExecutor chain...\u001b[0m\n\u001b[32;1m\u001b[1;3m\nThought: I need to find out how many people live in Canada\nAction: Search\nAction Input: How many people live in Canada as of 2023\u001b[0m\nObservation: \u001b[36;1m\u001b[1;3mThe current population of Canada is 38,645,670 as of Wednesday, March 29, 2023, based on Worldometer elaboration of the latest United Nations data.\u001b[0m\nThought:\u001b[32;1m\u001b[1;3m I now know the final answer\nFinal Answer: Arrr, there be 38,645,670 people livin' in Canada as of 2023!\u001b[0m\n\n\u001b[1m> Finished chain.\u001b[0m"
}
```

##### What happened?

- In a matter of few seconds, we've deployed our API on Jina AI Cloud 🎉
- The API is serverless and scalable, so we can scale up the API to handle more requests. 
- You might observe a delay in the first request, that's due to the warm-up time of the API. Subsequent requests will be faster.
- The API includes a Swagger UI and the OpenAPI specification, so it can be easily integrated with other services. 
- Now, other agents can integrate with your agents on Jina AI Cloud thanks to the [OpenAPI Agent](https://python.langchain.com/en/latest/modules/agents/toolkits/examples/openapi.html) 💡

