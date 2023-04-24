from lcserve import serving
from typing import Union, List

from langchain import OpenAI
from chain import get_qna_chain, load_pdf_content


@serving
def ask(urls: Union[List[str], str], question: str) -> str:
    content = load_pdf_content(urls)
    chain = get_qna_chain(OpenAI())
    return chain.run(input_document=content, question=question)
