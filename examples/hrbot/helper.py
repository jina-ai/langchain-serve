import json
import os
from typing import List

from langchain.llms import OpenAI
from langchain.tools import Tool

try:
    from gdrive import download_file
except ImportError:
    from .gdrive import download_file


def load_tools_from_disk(llm: OpenAI, path: str):
    from langchain.chains import RetrievalQA
    from langchain.embeddings.openai import OpenAIEmbeddings
    from langchain.vectorstores import FAISS

    tools = []

    embeddings = OpenAIEmbeddings()
    for root, _, files in os.walk(path):
        for file in files:
            if file.endswith(".faiss"):
                index_name = file.replace(".faiss", "")
                faiss_index = FAISS.load_local(
                    folder_path=root, embeddings=embeddings, index_name=index_name
                )
                print(f'Loaded {index_name} from local')
                docs_chain = RetrievalQA.from_chain_type(
                    llm=llm, chain_type="stuff", retriever=faiss_index.as_retriever()
                )
                # read a json file with the name *-tool.json and create a tool for it
                tool_json = os.path.join(root, f"{index_name}-tool.json")
                if os.path.exists(tool_json):
                    with open(tool_json, "r") as f:
                        tool_dict = json.load(f)
                    tools.append(
                        Tool(
                            name=tool_dict["name"],
                            func=docs_chain.run,
                            description=tool_dict["description"],
                            return_direct=True,
                        )
                    )

    return tools


def index_pdf(llm, name: str, path: str, url: str = None):
    from langchain.chains import RetrievalQA
    from langchain.document_loaders import PyPDFLoader
    from langchain.embeddings.openai import OpenAIEmbeddings
    from langchain.vectorstores import FAISS

    embeddings = OpenAIEmbeddings()
    index_name = name.replace(" ", "_").lower()

    try:
        faiss_index = FAISS.load_local(
            folder_path=path, embeddings=embeddings, index_name=index_name
        )
        print(f'Loaded {index_name} from local')
    except Exception as e:
        print(f'Failed to load {index_name} from local, building from scratch')
        loader = PyPDFLoader(url)
        pages = loader.load_and_split()
        print(f'Total {len(pages)} pages indexed')
        faiss_index = FAISS.from_documents(pages, embedding=embeddings)
        faiss_index.save_local(folder_path=path, index_name=index_name)

    return RetrievalQA.from_chain_type(
        llm=llm, chain_type="stuff", retriever=faiss_index.as_retriever()
    )


def prune_files_on_disk(path: str, tool_paths: List[str]):
    """
    Each tool_path is in format {name}-tool.json.
    We need to extract `name` from each tool_path. Each {name}.faiss, {name}.pkl, {name}-tool.json should be kept in `path` folder.
    All other files should be deleted from `path` folder.
    """

    tool_names = [
        os.path.basename(tool_path).replace("-tool.json", "")
        for tool_path in tool_paths
    ]

    for root, _, files in os.walk(path):
        for file in files:
            if (
                file.endswith(".faiss")
                or file.endswith(".pkl")
                or file.endswith("-tool.json")
            ):
                if (
                    file.replace(".faiss", "")
                    .replace(".pkl", "")
                    .replace("-tool.json", "")
                    not in tool_names
                ):
                    os.remove(os.path.join(root, file))


def index_pdfs_and_save(
    service,
    pdf_files: List[dict],
    basedir: str,
    llm: OpenAI,
):
    base_description = """\
Useful when you need to answer questions about {description}. \
Input should be a a fully formed question."""
    tools_stored = []

    for pdf_file in pdf_files:
        pdf_name: str = pdf_file['name']
        tool_name = pdf_name.lstrip('/').rstrip('.pdf')

        pdf_file_path = os.path.join(basedir, pdf_name.lstrip('/').lower())
        name = pdf_file_path.replace(" ", "_").lower() + '.' + pdf_file['md5']

        if not os.path.exists(os.path.dirname(name)):
            os.makedirs(os.path.dirname(name))

        # If index cache doesn't exist, download & index
        if not os.path.exists(os.path.join(basedir, f'{name}.faiss')):
            download_file(service, pdf_file['id'], pdf_file_path)
            chain = index_pdf(llm, name=name, path=basedir, url=pdf_file_path)
            os.remove(pdf_file_path)
        else:
            chain = index_pdf(llm, name=name, path=basedir)

        tool = Tool(
            name=tool_name,
            func=chain.run,
            description=base_description.format(
                description=pdf_file['description'] or tool_name
            ),
            return_direct=True,
        )
        # save the tool to disk
        tool_json = os.path.join(basedir, f"{name}-tool.json")
        with open(tool_json, "w") as f:
            f.write(tool.json(exclude={"func", "coroutine"}))

        tools_stored.append(tool_json)

    prune_files_on_disk(basedir, tools_stored)
