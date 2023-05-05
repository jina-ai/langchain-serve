import click


async def converse(host: str, verbose: bool = False):
    import aiohttp
    from dotenv import dotenv_values

    _next_prompt_msg = 'Waiting for next prompt, OR pass "exit" to exit.'
    _bot = click.style('Bot:', fg='green', bold=True)
    _answer_bot = click.style('Bot (Answer):', fg='green', bold=True, blink=True)
    _you = click.style('You:', fg='blue', bold=True, blink=True)

    def _echo_if_verbose(msg):
        if verbose:
            click.echo(msg)

    def _bot_said(msg: str, answer=False):
        click.echo(f'{_answer_bot} {msg}' if answer else f'{_bot} {msg}', color=True)

    def _you_prompted():
        return click.prompt(f'{_you}', prompt_suffix=' ')

    try:
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(f'{host}/converse') as ws:
                _bot_said('Please pass the url of the dataframe.')
                _url = _you_prompted()

                _bot_said('Please pass the path of the .env file to read.')
                _env_file = _you_prompted()
                _envs = dotenv_values(_env_file)
                _input_json = {'url': _url, 'envs': _envs}
                _echo_if_verbose(f'Sending {_input_json}')
                await ws.send_json(_input_json)

                # wait for the app to send the dataframe info
                response = await ws.receive_json()
                _echo_if_verbose(f'Received {response}')
                if 'message' not in response:
                    raise ValueError(f'Unexpected response: {response}')
                _bot_said(response['message'])

                # start the conversation
                while True:
                    user_input = _you_prompted()
                    _prompt = {'prompt': user_input}
                    _echo_if_verbose(f'Sending {_prompt}')
                    await ws.send_json(_prompt)

                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            response = msg.json()
                            _echo_if_verbose(f'Received {response}')
                            if 'message' in response:
                                _bot_said(response['message'])
                                if response['message'] == _next_prompt_msg:
                                    break
                            elif 'answer' in response:
                                _bot_said(response['answer'], answer=True)
                            elif 'result' in response:
                                _bot_said(response['result'])
                                if response['result'] == 'Bye!':
                                    return
                            else:
                                _bot_said(response)
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            break
    except KeyboardInterrupt:
        pass
    except Exception as e:
        click.echo(e, err=True)


if __name__ == "__main__":
    converse(host='ws://localhost:8000', verbose=False)
