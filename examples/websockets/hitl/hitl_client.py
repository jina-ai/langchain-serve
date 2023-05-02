import asyncio
import os
from typing import Dict

import aiohttp
from pydantic import BaseModel, ValidationError


class Response(BaseModel):
    result: str
    error: str
    stdout: str


class HumanPrompt(BaseModel):
    prompt: str


async def hitl_client(url: str, name: str, question: str, envs: Dict = {}):
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(f'{url}/{name}') as ws:
            print(f'Connected to {url}/{name}.')

            await ws.send_json(
                {
                    "question": question,
                    "envs": envs if envs else {},
                }
            )

            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    if msg.data == 'close cmd':
                        await ws.close()
                        break
                    else:
                        try:
                            response = Response.parse_raw(msg.data)
                            print(response.result, end='')
                        except ValidationError:
                            try:
                                prompt = HumanPrompt.parse_raw(msg.data)
                                answer = input(prompt.prompt + '\n')
                                await ws.send_str(answer)
                            except ValidationError:
                                print(f'Unknown message: {msg.data}')

                elif msg.type == aiohttp.WSMsgType.ERROR:
                    print('ws connection closed with exception %s' % ws.exception())
                else:
                    print(msg)


asyncio.run(
    hitl_client(
        url='wss://langchain-72aff35874.wolf.jina.ai',
        name='hitl',
        question='What is Eric Zhu\'s birthday?',
        envs={
            'OPENAI_API_KEY': os.environ['OPENAI_API_KEY'],
        },
    )
)
