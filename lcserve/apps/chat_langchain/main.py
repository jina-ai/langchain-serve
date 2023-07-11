"""Main entrypoint for the app."""
import logging
from pathlib import Path
from typing import List
from typing import Optional

import openai
from docarray import DocList
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.templating import Jinja2Templates
from langchain.embeddings import OpenAIEmbeddings
from langchain.retrievers.docarray import DocArrayRetriever
from langchain.schema import Document as LCDocument
from langchain.vectorstores import VectorStore

from callback import QuestionGenCallbackHandler, StreamingLLMCallbackHandler
from query_data import get_chain
from schemas import ChatResponse
from schemas import Document

# openai.proxy = {'https': 'http://127.0.0.1:7890', 'http': 'http://127.0.0.1:7890'}

app = FastAPI()
templates = Jinja2Templates(directory="templates")
vectorstore: Optional[VectorStore] = None


class DocArrayRetrieverWithFix(DocArrayRetriever):
    async def aget_relevant_documents(self, query: str) -> List[LCDocument]:
        return self.get_relevant_documents(query)


@app.on_event("startup")
async def startup_event():
    logging.info("loading vectorstore")
    if not Path("lc-serve-toy-data.pickle").exists():
        raise ValueError("lc-serve-toy-data.pickle does not exist, please run ingest.py first")
    global retriever
    dl = DocList[Document].load_binary('lc-serve-toy-data.pickle', compress=None, protocol='pickle')
    from docarray.index import InMemoryExactNNIndex
    store = InMemoryExactNNIndex[Document]()
    store.index(dl)
    embeddings = OpenAIEmbeddings()
    retriever = DocArrayRetrieverWithFix(index=store, embeddings=embeddings, search_field='embedding',
                                         content_field='page_content')


@app.get("/")
async def get(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.websocket("/chat")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    question_handler = QuestionGenCallbackHandler(websocket)
    stream_handler = StreamingLLMCallbackHandler(websocket)
    chat_history = []
    qa_chain = get_chain(retriever, question_handler, stream_handler)
    # Use the below line instead of the above line to enable tracing
    # Ensure `langchain-server` is running
    # qa_chain = get_chain(vectorstore, question_handler, stream_handler, tracing=True)

    while True:
        try:
            # Receive and send back the client message
            question = await websocket.receive_text()
            resp = ChatResponse(sender="you", message=question, type="stream")
            await websocket.send_json(resp.dict())

            # Construct a response
            start_resp = ChatResponse(sender="bot", message="", type="start")
            await websocket.send_json(start_resp.dict())

            result = await qa_chain.acall(
                {"question": question, "chat_history": chat_history}
            )
            chat_history.append((question, result["answer"]))

            end_resp = ChatResponse(sender="bot", message="", type="end")
            await websocket.send_json(end_resp.dict())
        except WebSocketDisconnect:
            logging.info("websocket disconnect")
            break
        except Exception as e:
            logging.error(e)
            resp = ChatResponse(
                sender="bot",
                message="Sorry, something went wrong. Try again.",
                type="error",
            )
            await websocket.send_json(resp.dict())


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=9000)
