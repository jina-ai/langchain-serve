# langchain-serve
Langchain Apps on Production using Jina


[Langchain docs recommend a few options for deploying apps](https://langchain.readthedocs.io/en/latest/deployments.html). This repo is an attempt to deploy Langchain apps using Jina.

## Examples

| Example | LangChain Docs | Description |
| ------- | ----------- | ----------- |
| [LLM Chain](examples/llm_chain.md) | [Link](https://langchain.readthedocs.io/en/latest/modules/chains/getting_started.html#query-an-llm-with-the-llmchain) | Expose `Chain` as RESTful/gRPC/WebSocket API locally |
| [Simple Sequential Chain](examples/simple_sequential_chain.md) | [Link](https://langchain.readthedocs.io/en/latest/modules/chains/generic/sequential_chains.html#simplesequentialchain) | Expose `Chain` as RESTful/gRPC/WebSocket API locally |
| [Sequential Chain](examples/sequential_chain.md) | [Link](https://langchain.readthedocs.io/en/latest/modules/chains/generic/sequential_chains.html#sequential-chain) | Expose `Chain` as RESTful/gRPC/WebSocket API locally |
| [LLM Math Chain](examples/llm_math.md) | [Link](https://langchain.readthedocs.io/en/latest/modules/chains/examples/llm_math.html) | Expose `Chain` as RESTful/gRPC/WebSocket API locally |
| [LLM Requests Chain](examples/llm_requests_chain.md) | [Link](https://langchain.readthedocs.io/en/latest/modules/chains/examples/llm_requests.html) | Expose `Chain` as RESTful/gRPC/WebSocket API locally |
| [Custom Chain](examples/custom_chain.md) | [Link](https://langchain.readthedocs.io/en/latest/modules/chains/getting_started.html#create-a-custom-chain-with-the-chain-class) | Expose `Chain` as RESTful/gRPC/WebSocket API locally |
| | TBD | Expose `Agent` as RESTful/gRPC/WebSocket API locally |
| | TBD | Branching `Chains` |
| | TBD | Streaming/concurrent requests |
| | TBD | Pushing `Chains` as `Executors` to Jina Hub |
| | TBD | Serve `Chains` on JCloud |
| | TBD | Serverless `Chains` on JCloud |
| | TBD | Serve `Agents` on JCloud |
| | TBD | Serverless `Agents` on JCloud |
