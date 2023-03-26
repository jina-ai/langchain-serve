# Deploy Langchain Apps on Jina 🚀

[Jina](https://github.com/jina-ai/jina) is an open-source framework to build, deploy & manage machine learning applications at scale. 

## Agents on Jina 🤖☁️

Langchain agents use LLMs to determine the actions to be taken in what order. An action can either be using a tool and observing its output, or returning to the user. [Read more about agents here](https://python.langchain.com/en/latest/modules/agents/getting_started.html).

Langchain agents can be used as standalone applications when used locally, this project aims to deploy Langchain agents on Cloud to make them accessible to everyone via RESTful APIs. Jina AI Cloud also allows to extend agents using gRPC and WebSocket APIs.

### Streamlit playground 🕹️🎮

You can try out Langchain Agents on our Playground URL. The streamlit playground is hosted on Jina AI Cloud and allows you to interact with the agent which accepts the following inputs:

- **Agent Types:** Choose from different agent types that Langchain supports. You can find a list of these types along with a description [here](https://python.langchain.com/en/latest/modules/agents/agents.html).

- **Tools:** Choose from different tools that Langchain supports. Some tools may require an API token or other related arguments. You can find a list of these tools along with a description [here](https://python.langchain.com/en/latest/modules/agents/tools.html).

To use the playground, simply type your input in the text box provided to get the agent's output and chain of thought. Enjoy exploring Langchain's capabilities!

### Interact with agents using RESTful APIs 🤖🌐

In addition to streamlit, you can also use our API to interact with the agents. 

#### [Zero-shot React Description agent with SerpAPI and Calculator](https://python.langchain.com/en/latest/modules/agents/getting_started.html)

```bash
export OPENAI_API_KEY=sk-***
export SERPAPI_API_KEY=***

curl -sX POST 'http://langchain.wolf.jina.ai/api/run' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  --data-raw '{
    "text": "Who is Leo DiCaprios girlfriend? What is her current age raised to the 0.43 power",
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

#### One more example here TBD




## Chains on Jina 📦🚀

Chains in langchain allow users to combine 

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