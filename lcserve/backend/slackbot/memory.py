from enum import Enum

from langchain.memory import ChatMessageHistory

try:
    from .helper import grouper
except ImportError:
    from helper import grouper


class MemoryMode(str, Enum):
    SUMMARY = "summary"
    SUMMARY_BUFFER = "summary_buffer"
    LLAMA_SUMMARY = "llama_summary"


def get_memory(history: ChatMessageHistory, mode=MemoryMode.SUMMARY_BUFFER):
    from langchain.llms import OpenAI

    if mode == MemoryMode.SUMMARY:
        from langchain.memory import ConversationSummaryMemory

        memory = ConversationSummaryMemory.from_messages(
            llm=OpenAI(temperature=0, verbose=True),
            chat_memory=history,
            memory_key="chat_history",
        )

    elif mode == MemoryMode.SUMMARY_BUFFER:
        from langchain.memory import ConversationSummaryBufferMemory

        memory = ConversationSummaryBufferMemory(
            llm=OpenAI(temperature=0, verbose=True),
            max_token_limit=2000,
            memory_key="chat_history",
            return_messages=True,
        )

        for first, second in grouper(history.messages, 2):
            outputs = (
                {second.role: second.content}
                if second is not None
                else {first.role: first.content}
            )
            memory.save_context(
                inputs={first.role: first.content},
                outputs=outputs,
            )

    elif mode == MemoryMode.LLAMA_SUMMARY:
        from llama_index import ListIndex

        try:
            from .llama import GPTMultiUserChatMemory
        except ImportError:
            from llama import GPTMultiUserChatMemory

        memory = GPTMultiUserChatMemory(
            index=ListIndex([]),
            llm=OpenAI(temperature=0, verbose=True),
            chat_memory=history,
            memory_key="chat_history",
            return_messages=True,
        )

        for first, second in grouper(history.messages, 2):
            outputs = (
                {second.role: second.content}
                if second is not None
                else {first.role: first.content}
            )
            memory.save_context(
                inputs={first.role: first.content},
                outputs=outputs,
            )

    return memory
