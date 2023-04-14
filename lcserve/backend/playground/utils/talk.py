from typing import Dict, Tuple

import requests

LANGCHAIN_API_HOST = 'http://localhost:8080/run'


def agent_params_from_input(
    selected_params: Dict[str, Dict[str, str]], agent_type: str
) -> Dict:
    tools = {'tool_names': []}
    for param in selected_params.values():
        tools['tool_names'].append(param['api'])
        tools.update(**{k: v for k, v in param.items() if k != 'api'})

    return {
        'tools': tools,
        'agent': agent_type,
        'verbose': True,
    }


def talk_to_agent(
    question: str,
    selected_params: Dict[str, Dict[str, str]],
    openai_token: str,
    agent_type: str,
    host: str = LANGCHAIN_API_HOST,
) -> Tuple[str, str]:
    if not host.endswith('/run'):
        host = f'{host}/run'

    response = requests.post(
        host,
        headers={'accept': 'application/json', 'Content-Type': 'application/json'},
        json={
            'text': question,
            'html': True,
            'parameters': agent_params_from_input(selected_params, agent_type),
            'envs': {'OPENAI_API_KEY': openai_token},
        },
    )
    _response = response.json()
    if 'result' in _response and 'chain_of_thought' in _response:
        return _response['result'], _response['chain_of_thought']
    elif 'result' in _response:
        return _response['result'], None

    return _response, None
