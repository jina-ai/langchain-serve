"""Load html from files, clean up, split, ingest into Weaviate."""
from langchain.document_loaders import ReadTheDocsLoader
from langchain.embeddings import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from docarray import DocList
from langchain.vectorstores.docarray.base import DocArrayIndex


def ingest_docs():
    """Get documents from web pages."""
    loader = ReadTheDocsLoader("langchain.readthedocs.io")
    raw_documents = loader.load()
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
    )
    documents = text_splitter.split_documents(raw_documents)
    doc_cls = DocArrayIndex._get_doc_cls()
    index = DocList[doc_cls](
        [doc_cls(text=d.page_content, metadata=d.metadata)
         for d in documents])
    index.embedding=OpenAIEmbeddings().embed_documents(index.text)
    # this works by adding global claim at
    # /lib/python3.8/site-packages/langchain/vectorstores/docarray/base.py::51
    index.save_binary('simple-dl.pickle', compress=None, protocol='pickle')


if __name__ == "__main__":
    ingest_docs()
