from langchain.chains import ConversationalRetrievalChain
from langchain.callbacks.manager import AsyncCallbackManager
from langchain.llms import OpenAI
from langchain.chains.chat_vector_db.prompts import (CONDENSE_QUESTION_PROMPT, QA_PROMPT)
from langchain.chains.question_answering import load_qa_chain
from langchain.chains.llm import LLMChain


def get_chain(jac_storage_name, question_handler, stream_handler) -> ConversationalRetrievalChain:
    manager = AsyncCallbackManager([])
    question_manager = AsyncCallbackManager([question_handler])
    stream_manager = AsyncCallbackManager([stream_handler])

    question_gen_llm = OpenAI(
        temperature=0,
        callback_manager=question_manager,
        verbose=True
    )

    streaming_llm = OpenAI(
        temperature=0,
        streaming=True,
        callback_manager=stream_manager,
        verbose=True
    )

    question_generator = LLMChain(
        llm=question_gen_llm, prompt=CONDENSE_QUESTION_PROMPT, callback_manager=manager
    )

    doc_chain = load_qa_chain(
        streaming_llm, chain_type='stuff', prompt=QA_PROMPT, callback_manager=manager
    )

    qa = ConversationalRetrievalChain(
        retriever=jac_storage_name.as_retriever(),
        combine_docs_chain=doc_chain,
        question_generator=question_generator,
        callback_manger=manager,
        return_source_documents=True,
        verbose=True
    )
    return qa
