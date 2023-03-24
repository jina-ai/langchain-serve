from typing import Dict


def agent_params_from_input(selected_params: Dict[str, Dict[str, str]]) -> Dict:
    tools = {'tool_names': []}
    for param in selected_params.values():
        tools['tool_names'].append(param['api'])
        tools.update(**{k: v for k, v in param.items() if k != 'api'})

    return {
        'tools': tools,
        'agent': 'zero-shot-react-description',
        'verbose': True,
    }
