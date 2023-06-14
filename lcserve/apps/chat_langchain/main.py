"""Main entrypoint for the app."""
import logging
import pickle
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.templating import Jinja2Templates
from langchain.vectorstores import VectorStore
from langchain.embeddings import OpenAIEmbeddings

from callback import QuestionGenCallbackHandler, StreamingLLMCallbackHandler
from query_data import get_chain
from schemas import ChatResponse, DocumentWithEmbedding
from langchain.vectorstores.docarray import DocArrayInMemorySearch
from docarray import DocList

import openai
openai.proxy = {'https': 'http://127.0.0.1:7890', 'http': 'http://127.0.0.1:7890'}

app = FastAPI()
templates = Jinja2Templates(directory="templates")
vectorstore: Optional[VectorStore] = None


@app.on_event("startup")
async def startup_event():
    logging.info("loading vectorstore")
    if not Path("simple-dl.pickle").exists():
        raise ValueError("simple-dl.pkl does not exist, please run ingest.py first")
    global vectorstore
    dl = DocList[DocumentWithEmbedding].load_binary('simple-dl.pickle', compress=None, protocol='pickle')
    from docarray.index import InMemoryExactNNIndex
    index = InMemoryExactNNIndex[DocumentWithEmbedding](dl)
    logging.info(f'get schema {index._schema}')
    embedding = OpenAIEmbeddings()
    vectorstore = DocArrayInMemorySearch(doc_index=index, embedding=embedding)


@app.get("/")
async def get(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.websocket("/chat")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    question_handler = QuestionGenCallbackHandler(websocket)
    stream_handler = StreamingLLMCallbackHandler(websocket)
    chat_history = []
    qa_chain = get_chain(vectorstore, question_handler, stream_handler)
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
