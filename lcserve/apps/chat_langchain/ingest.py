"""Load html from files, clean up, split, ingest into Weaviate."""
import click
from docarray import DocList
from langchain.document_loaders import ReadTheDocsLoader
from langchain.embeddings import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter

from schemas import Document


@click.command()
@click.argument('pathname', type=click.Path(exists=True))
def ingest_docs(pathname):
    """Get documents from web pages."""
    loader = ReadTheDocsLoader(pathname)
    raw_documents = loader.load()
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
    )
    documents = text_splitter.split_documents(raw_documents)
    dl = DocList[Document](
        [Document(page_content=d.page_content, metadata=d.metadata)
         for d in documents])
    dl.embedding = OpenAIEmbeddings().embed_documents(dl.page_content)
    dl.save_binary('lc-serve-toy-data.pickle')


if __name__ == "__main__":
    ingest_docs()
