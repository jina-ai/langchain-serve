import json
import asyncio
from typing import Dict, Union

import click
import aiohttp
from pydantic import BaseModel, ValidationError

from user_input import UserInput, prompt_user


class Response(BaseModel):
    result: str
    error: str
    stdout: str


class HumanPrompt(BaseModel):
    prompt: str


class ThoughtsCommands(BaseModel):
    thoughts: Dict[str, str]
    command: Dict[str, Union[str, Dict[str, str]]]


async def autogpt(user_input: UserInput, verbose: bool = False):
    _bot = click.style('Bot:', fg='green', bold=True)
    _dim_msg = lambda msg: click.style(msg, fg='green', bold=False, dim=True)
    _thought = click.style('Thought:', fg='green', bold=True, blink=True)
    _command = click.style('Command:', fg='green', bold=True, blink=True)
    _you = click.style('You:', fg='blue', bold=True, blink=True)

    def _echo_if_verbose(msg):
        if verbose:
            click.echo(msg)

    def _bot_said(msg: str, cot=False):
        if cot:
            click.echo(_dim_msg(msg), color=True, nl=False)
        else:
            click.echo(f'\n{_bot} {msg}', color=True, nl=True)

    def _bot_thought(msg: Dict):
        _json_msg = json.dumps(msg, indent=4)
        click.echo(f'\n{_thought} {_json_msg}', color=True)

    def _bot_command(msg: Dict):
        _json_msg = json.dumps(msg, indent=4)
        click.echo(f'\n{_command} {_json_msg}', color=True)

    def _you_prompted():
        return click.prompt(f'{_you}', prompt_suffix=' ')

    try:
        async with aiohttp.ClientSession() as session:
            _url = f'{user_input.host}/{user_input.endpoint}'
            async with session.ws_connect(_url) as ws:
                _bot_said(f'Connected to {_url}.')
                _input_json = {
                    "name": user_input.name,
                    "role": user_input.role,
                    "goals": user_input.goals,
                    "human_in_the_loop": user_input.human_in_the_loop,
                    "envs": user_input.envs,
                }
                _echo_if_verbose(f'Sending: {_input_json}')
                await ws.send_json(_input_json)

                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        _data = msg.data
                        _echo_if_verbose(f'Received: {_data}')

                        if _data == 'close cmd':
                            await ws.close()
                            break
                        else:
                            try:
                                response = Response.parse_raw(_data)
                                _bot_said(response.result, cot=True)
                            except ValidationError:
                                try:
                                    prompt = HumanPrompt.parse_raw(msg.data)
                                    _bot_said(prompt.prompt)
                                    feedback = _you_prompted()
                                    _echo_if_verbose(f'Sending: {feedback}')
                                    await ws.send_str(feedback)
                                except ValidationError:
                                    try:
                                        thoughts_commands = ThoughtsCommands.parse_raw(
                                            msg.data
                                        )
                                        _bot_thought(thoughts_commands.thoughts)
                                        _bot_command(thoughts_commands.command)

                                    except ValidationError:
                                        print(f'Unknown: {msg.data}')

                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        print('ws connection closed with exception %s' % ws.exception())
                    else:
                        print(msg)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        click.echo(e, err=True)


async def play(verbose: bool = False):
    try:
        user_input = prompt_user()
    except ValidationError as e:
        print(e)
        return
    except KeyboardInterrupt:
        return

    await autogpt(user_input=user_input, verbose=verbose)


if __name__ == '__main__':
    asyncio.run(play())
