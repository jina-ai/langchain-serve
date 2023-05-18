import asyncio
from typing import Dict

import nest_asyncio
from lcserve import serving, download_df
from fastapi import WebSocket

try:
    from pandasai import PandasAI
    from pandasai.llm.openai import OpenAI
except (ImportError, ModuleNotFoundError):
    print("PandasAI not installed. Please install using `pip install pandasai`")
    exit(1)

nest_asyncio.apply()

EXIT_PROMPT = "exit"


class ConversationalPandasAI(PandasAI):
    def __init__(self, websocket: WebSocket, **kwargs):
        self.websocket = websocket
        super().__init__(**kwargs)

    def log(self, message: str):
        super().log(message)
        asyncio.run(self.websocket.send_json({"message": message}))


@serving
def ask(url: str, prompt: str, **kwargs) -> str:
    df = download_df(url)
    llm = OpenAI()
    pandas_ai = PandasAI(llm, verbose=True)
    return pandas_ai.run(df, prompt=prompt)


@serving(websocket=True)
async def converse(url: str, **kwargs) -> str:
    websocket: WebSocket = kwargs.get("websocket")
    try:
        df = download_df(url)
    except Exception as e:
        await websocket.send_json({"message": f"Error downloading dataframe: {e}"})
        return

    await websocket.send_json(
        {"message": f"Downloaded dataframe with shape {df.shape}. Send me a prompt!"}
    )

    while True:
        prompt_input: Dict = await websocket.receive_json()
        prompt = prompt_input.get("prompt")
        if prompt is None or prompt.lower() == EXIT_PROMPT:
            return "Bye!"
        llm_args = prompt_input.get("llm_args", {})
        llm = OpenAI(**llm_args)
        pandas_ai = ConversationalPandasAI(websocket=websocket, llm=llm, verbose=True)
        answer = pandas_ai.run(df, prompt=prompt)
        await websocket.send_json({"answer": answer})
        await websocket.send_json(
            {"message": 'Waiting for next prompt, OR pass "exit" to exit.'}
        )
