"""Load html from files, clean up, split, ingest into Weaviate."""
import pickle

from langchain.document_loaders import ReadTheDocsLoader
from langchain.embeddings import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
# from langchain.vectorstores.faiss import FAISS
from docarray import DocList
from schemas import DocumentWithEmbedding
import numpy as np

def ingest_docs():
    """Get documents from web pages."""
    loader = ReadTheDocsLoader("langchain.readthedocs.io")
    raw_documents = loader.load()
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
    )
    documents = text_splitter.split_documents(raw_documents)
    index = DocList[DocumentWithEmbedding](
        [DocumentWithEmbedding(page_content=d.page_content, embedding=np.random.random(10), metadata=d.metadata)
         for d in documents])
    print(f'schema is {index._schema}')

    # OpenAIEmbeddings().embed_documents(index.page_content)
    index.save_binary('simple-dl.pickle', compress=None, protocol='pickle')

    # vectorstore = FAISS.from_documents(documents, embeddings)
    #
    # # Save vectorstore
    # with open("vectorstore.pkl", "wb") as f:
    #     pickle.dump(vectorstore, f)


if __name__ == "__main__":
    ingest_docs()
