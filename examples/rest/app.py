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
    print(ask("What is the capital of France?"))
