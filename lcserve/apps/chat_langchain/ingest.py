"""Load html from files, clean up, split, ingest into Weaviate."""
from docarray import DocList
from langchain.document_loaders import ReadTheDocsLoader
from langchain.embeddings import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter

from schemas import Document


def ingest_docs():
    """Get documents from web pages."""
    loader = ReadTheDocsLoader("langchain.readthedocs.io")
    raw_documents = loader.load()
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
    )
    documents = text_splitter.split_documents(raw_documents)
    index = DocList[Document](
        [Document(page_content=d.page_content, metadata=d.metadata)
         for d in documents])
    index.embedding = OpenAIEmbeddings().embed_documents(index.page_content)
    index.save_binary('simple-dl.pickle', compress=None, protocol='pickle')


if __name__ == "__main__":
    ingest_docs()
