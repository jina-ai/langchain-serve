import os

import requests
from langchain.chains import RetrievalQA
from langchain.chat_models import ChatOpenAI
from langchain.document_loaders import TextLoader
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.text_splitter import CharacterTextSplitter
from langchain.vectorstores import FAISS

from lcserve import job


@job(timeout=100, backofflimit=3)
def my_job(doc_name: str, question: str):
    print("Starting the job ...")

    url = f"https://raw.githubusercontent.com/langchain-ai/langchain/master/docs/extras/modules/{doc_name}"
    response = requests.get(url)
    data = response.text
    with open("doc.txt", "w") as text_file:
        text_file.write(data)
    print("Download text complete !!")

    embeddings = OpenAIEmbeddings()
    loader = TextLoader("doc.txt", encoding="utf8")
    text_splitter = CharacterTextSplitter()
    docs = text_splitter.split_documents(loader.load())
    faiss_index = FAISS.from_documents(docs, embedding=embeddings)
    faiss_index.save_local(
        folder_path=os.path.dirname(os.path.abspath(__file__)), index_name="index"
    )
    print("Index complete !!")

    llm = ChatOpenAI(temperature=0)
    qa_chain = RetrievalQA.from_chain_type(llm, retriever=faiss_index.as_retriever())
    result = qa_chain({"query": question})

    print(f"\nQuestion: {question}\nAnswer: {result['result']}]\n")


if __name__ == "__main__":
    my_job(
        "paul_graham_essay.txt", "Why Paul flew up to Oregon to visit her mom regularly"
    )
