import logging
from lcserve import serving
from fastapi import WebSocket, WebSocketDisconnect
from callbacks import QuestionGenCallbackHandler, StreamingLLMCallbackHandler
from chain import get_chain
from schema import ChatResponse
from pathlib import Path
import pickle


@serving(websocket=True)
async def chat(websocket: WebSocket):
    await websocket.accept()
    jac_storage_name = 'vectorstore.pkl'
    if not Path(jac_storage_name).exists():
        raise ValueError(f'`{jac_storage_name}` does not exist')
    with open(jac_storage_name, 'rb') as f:
        global vectorstore
        vectorstore = pickle.load(f)
    question_handler = QuestionGenCallbackHandler(websocket)
    stream_handler = StreamingLLMCallbackHandler(websocket)
    chat_history = []
    qa_chain = get_chain(vectorstore, question_handler, stream_handler)

    while True:
        try:
            # Receive and send back the client message
            question = await websocket.receive_text()
            resp = ChatResponse(sender='you', message=question, type='stream')
            await websocket.send_json(resp.dict())

            # Construct a response
            start_resp = ChatResponse(sender='bot', message='', type='start')
            await websocket.send_json(start_resp.dict())

            result = await qa_chain.acall(
                {'question': question, 'chat_history': chat_history}
            )
            chat_history.append((question, result['answer']))

            end_resp = ChatResponse(sender='bot', message='', type='end')
            await websocket.send_json(end_resp.dict())
        except WebSocketDisconnect as e:
            logging.info(f'websocket disconnect. {e}')
            break
        except Exception as e:
            logging.error(e)
            resp = ChatResponse(
                sender='bot',
                message='Sorry, something went wrong. Try again.',
                type='error'
            )
            await websocket.send_json(resp.dict())
