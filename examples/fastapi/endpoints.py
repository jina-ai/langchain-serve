import os
from typing import Union

from fastapi import FastAPI

app = FastAPI()


@app.get("/status")
def read_root():
    return {"Hello": "World"}


@app.get("/items/{item_id}")
def read_item(item_id: int, q: Union[str, None] = None):
    return {"item_id": item_id, "q": q}


@app.get("/assert")
def assert_env():
    if 'OPENAI_API_KEY' not in os.environ or 'SERP_API_KEY' not in os.environ:
        return {"assert": "failed"}
    return {"assert": "ok"}
