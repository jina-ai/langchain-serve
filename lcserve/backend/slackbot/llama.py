from typing import Any, Dict, List

from llama_index.langchain_helpers.memory_wrapper import GPTIndexChatMemory
from langchain.schema import ChatMessage


class GPTMultiUserChatMemory(GPTIndexChatMemory):
    @staticmethod
    def msg_to_txt(msg: ChatMessage) -> str:
        return f'{msg.role}: {msg.content}'

    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, str]) -> None:
        from llama_index import Document as LlamaDocument
        from llama_index.utils import get_new_id

        first_role = list(inputs.keys())[0]
        first_content = list(inputs.values())[0]
        first_msg = ChatMessage(role=first_role, content=first_content)
        first_message_id = get_new_id(set(self.id_to_message.keys()))
        self.chat_memory.messages.append(first_msg)
        self.id_to_message[first_message_id] = first_msg
        first_doc = LlamaDocument(
            text=GPTMultiUserChatMemory.msg_to_txt(first_msg),
            doc_id=first_message_id,
        )

        second_role = list(outputs.keys())[0]
        second_content = list(outputs.values())[0]
        second_msg = ChatMessage(role=second_role, content=second_content)
        second_message_id = get_new_id(set(self.id_to_message.keys()))
        self.chat_memory.messages.append(second_msg)
        self.id_to_message[second_message_id] = second_msg
        second_doc = LlamaDocument(
            text=GPTMultiUserChatMemory.msg_to_txt(second_msg),
            doc_id=second_message_id,
        )

        self.index.insert(first_doc)
        self.index.insert(second_doc)
