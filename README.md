# Langchain Apps on Production with Jina 🚀

[Jina](https://github.com/jina-ai/jina) is an open-source framework to build, deploy & manage machine learning applications at scale. 

## Agents on Jina 🤖☁️

Langchain agents use LLMs to determine the actions to be taken in what order. An action can either be using a tool and observing its output, or returning to the user. [Read more about agents here](https://python.langchain.com/en/latest/modules/agents/getting_started.html).

While Langchain agents can be standalone local applications, this project aims to make agents production-ready by 

  - Providing easy integration with Jina with RESTful/gRPC/WebSocket APIs.
  - Allowing seamless deployments on Jina AI Cloud ensuring high availability and scalability. 
  - Autoscaled to scale up and down your agents based on the load.
  - Exclusive access to Agents on Jina AI Cloud (coming soon)

### Playground 🕹️🎮🌐

You can try out Langchain Agents on our **[Playground URL](https://langchain.wolf.jina.ai/playground/)**. The streamlit playground is hosted on Jina AI Cloud and allows you to interact with the agent which accepts the following inputs:

- **[Agent Types](https://python.langchain.com/en/latest/modules/agents/agents.html):** Choose from different agent types that Langchain supports. 

- **[Tools](https://python.langchain.com/en/latest/modules/agents/tools.html):** Choose from different tools that Langchain supports. Some tools may require an API token or other related arguments.

To use the playground, simply type your input in the text box provided to get the agent's output and chain of thought. Enjoy exploring Langchain's capabilities! In addition to streamlit, you can also use our RESTful APIs on the playground to interact with the agents. 


### [Zero-shot React Description agent with SerpAPI and Calculator](https://python.langchain.com/en/latest/modules/agents/getting_started.html)

#### Streamlit Playground

![Streamlit Playground](.github/images/playground_one.gif)

#### RESTful API

```bash
export OPENAI_API_KEY=sk-***
export SERPAPI_API_KEY=***

curl -sX POST 'https://langchain.wolf.jina.ai/api/run' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  --data-raw '{
    "text": "Who is Leo DiCaprios girlfriend? What is her current age raised to the 0.43 power?",
    "parameters": {
        "tools": {
            "tool_names": ["serpapi", "llm-math"]
        },
        "agent": "zero-shot-react-description",
        "verbose": true
    },
    "envs": {
        "OPENAI_API_KEY": "'"${OPENAI_API_KEY}"'",
        "SERPAPI_API_KEY": "'"${SERPAPI_API_KEY}"'"
    }
}' | jq
``` 

```json
{
  "result": "Camila Morrone is Leo DiCaprio's girlfriend, and her current age raised to the 0.43 power is 3.6261260611529527.",
  "chain_of_thought": "\u001b[1m> Entering new AgentExecutor chain...\u001b[0m\u001b[32;1m\u001b[1;3m I need to find out the name of Leo's girlfriend and then use the calculator to calculate her age to the 0.43 power.Action: SearchAction Input: Leo DiCaprio girlfriend\u001b[0mObservation: \u001b[36;1m\u001b[1;3mDiCaprio met actor Camila Morrone in December 2017, when she was 20 and he was 43. They were spotted at Coachella and went on multiple vacations together. Some reports suggested that DiCaprio was ready to ask Morrone to marry him. The couple made their red carpet debut at the 2020 Academy Awards.\u001b[0mThought:\u001b[32;1m\u001b[1;3m I need to use the calculator to calculate her age to the 0.43 powerAction: CalculatorAction Input: 20^0.43\u001b[0mObservation: \u001b[33;1m\u001b[1;3mAnswer: 3.6261260611529527\u001b[0mThought:\u001b[32;1m\u001b[1;3m I now know the final answerFinal Answer: Camila Morrone is Leo DiCaprio's girlfriend, and her current age raised to the 0.43 power is 3.6261260611529527.\u001b[0m\u001b[1m> Finished chain.\u001b[0m"
}
```

### [Self Ask With Search](https://python.langchain.com/en/latest/modules/agents/implementations/self_ask_with_search.html)

#### Streamlit Playground

![Streamlit Playground](.github/images/playground_two.gif)

#### RESTful API

```bash
export OPENAI_API_KEY=sk-***
export SERPAPI_API_KEY=***

curl -sX POST 'https://langchain.wolf.jina.ai/api/run' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  --data-raw '{
    "text": "What is the hometown of the reigning mens U.S. Open champion?",
    "parameters": {
        "tools": {
            "tool_names": ["serpapi"]
        },
        "agent": "self-ask-with-search",
        "verbose": true
    },
    "envs": {
        "OPENAI_API_KEY": "'"${OPENAI_API_KEY}"'",
        "SERPAPI_API_KEY": "'"${SERPAPI_API_KEY}"'"
    }
}' | jq
```

```json
{
  "result": "El Palmar, Murcia, Spain",
  "chain_of_thought": "\u001b[1m> Entering new AgentExecutor chain...\u001b[0m\u001b[32;1m\u001b[1;3m Yes.Follow up: Who is the reigning mens U.S. Open champion?\u001b[0mIntermediate answer: \u001b[36;1m\u001b[1;3mCarlos Alcaraz Garfia\u001b[0m\u001b[32;1m\u001b[1;3mFollow up: What is Carlos Alcaraz Garfia's hometown?\u001b[0mIntermediate answer: \u001b[36;1m\u001b[1;3mCarlos Alcaraz Garfia was born on May 5, 2003, in El Palmar, Murcia, Spain to parents Carlos Alcaraz González and Virginia Garfia Escandón. He has three siblings.\u001b[0m\u001b[32;1m\u001b[1;3mSo the final answer is: El Palmar, Murcia, Spain\u001b[0m\u001b[1m> Finished chain.\u001b[0m"
}
```


## Chains on Jina 📦🚀

[Chains](https://python.langchain.com/en/latest/modules/chains/getting_started.html) in langchain allow users to combine components to create a single, coherent application. With Jina, 

- You can expose your `Chain` as RESTful/gRPC/WebSocket API.
- Enable `Chain`s to deploy & scale separately from the rest of your application with the help of Executors.
- Deploy your `Chain` on Jina AI Cloud and get exclusive access to Agents on Jina AI Cloud (coming soon)

### Examples

| Example | LangChain Docs | Description |
| ------- | ----------- | ----------- |
| [LLM Chain](examples/llm_chain.md) | [Link](https://langchain.readthedocs.io/en/latest/modules/chains/getting_started.html#query-an-llm-with-the-llmchain) | Expose `Chain` as RESTful/gRPC/WebSocket API locally |
| [Simple Sequential Chain](examples/simple_sequential_chain.md) | [Link](https://langchain.readthedocs.io/en/latest/modules/chains/generic/sequential_chains.html#simplesequentialchain) | Expose `Chain` as RESTful/gRPC/WebSocket API locally |
| [Sequential Chain](examples/sequential_chain.md) | [Link](https://langchain.readthedocs.io/en/latest/modules/chains/generic/sequential_chains.html#sequential-chain) | Expose `Chain` as RESTful/gRPC/WebSocket API locally |
| [LLM Math Chain](examples/llm_math.md) | [Link](https://langchain.readthedocs.io/en/latest/modules/chains/examples/llm_math.html) | Expose `Chain` as RESTful/gRPC/WebSocket API locally |
| [LLM Requests Chain](examples/llm_requests_chain.md) | [Link](https://langchain.readthedocs.io/en/latest/modules/chains/examples/llm_requests.html) | Expose `Chain` as RESTful/gRPC/WebSocket API locally |
| [Custom Chain](examples/custom_chain.md) | [Link](https://langchain.readthedocs.io/en/latest/modules/chains/getting_started.html#create-a-custom-chain-with-the-chain-class) | Expose `Chain` as RESTful/gRPC/WebSocket API locally |
| [Sequential Chains](examples/sequential_executors.md) | N/A | Build & scale `Chains` in separate `Executor`s |
| [Branching Chains](examples/branching.md) | N/A | Branching `Chains` in separate `Executor`s to allow parallel execution |


## What's coming next? 🤔

- [ ] Enable authorized, dedicated agents on Jina AI Cloud.
- [ ] Allow custom agents on Jina AI Cloud.
- [ ] Allow loading ChatGPT plugins.
- [ ] Agent examples with vector stores.
- [ ] Agent examples using gRPC and WebSocket APIs.