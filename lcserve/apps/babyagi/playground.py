import asyncio
import os
import sys
from typing import Dict

import aiohttp
import streamlit as st
from lcserve.backend.playground.utils.tools import ALL_TOOLS

# get file dir and add it to sys.path
cwd = os.path.dirname(os.path.realpath(__file__))
sys.path.append(cwd)

st.set_page_config(
    page_title='BabyAGI Playground',
    page_icon='⚡',
    layout='wide',
    initial_sidebar_state='auto',
)

st.sidebar.markdown('## OpenAI Token')
openai_token = st.sidebar.text_input(
    'Enter your OpenAI token:',
    placeholder='sk-...',
    type='password',
)

objective = st.text_input(
    'Type your objective:',
    placeholder='Who is Leo DiCaprio\'s girlfriend?',
)
first_task = st.text_input(
    'Type the first task:',
    placeholder='Who is Leo DiCaprio\'s girlfriend?',
)

max_iterations = st.number_input("Max iterations", value=1, min_value=1, step=1)

selected_tools = st.sidebar.multiselect('Select Predefined Tools:', ALL_TOOLS)
selected_tool_params = {}


def update_predefined_tool_params():
    global selected_tool_params
    for tool in selected_tools:
        api = ALL_TOOLS[tool]['api']
        selected_tool_params[tool] = {}
        selected_tool_params[tool]['api'] = api

        if len(ALL_TOOLS[tool]['args']) > 0:
            st.sidebar.write(f'`{tool}` parameters:')

            for tool_param in ALL_TOOLS[tool]['args']:
                param_value = st.sidebar.text_input(
                    'label',
                    key=f'{tool}_{tool_param}',
                    label_visibility='collapsed',
                    placeholder=tool_param,
                    type='password',
                )
                selected_tool_params[tool][tool_param] = param_value


def update_custom_tools():
    if 'custom_tools' not in st.session_state:
        st.session_state['custom_tools'] = []

    help_text = '''Tool(
    name=name,
    func=LLMChain(llm=llm, prompt=PromptTemplate.from_template(prompt)).run,
    descripton=description,
)
    '''

    with st.sidebar:
        with st.expander('Custom tool is added with ', expanded=False):
            st.code(help_text)

            if st.button('Add a custom tool'):
                st.session_state['custom_tools'].append(
                    {'name': '', 'prompt': '', 'description': ''}
                )

    _default_name = 'TODO'
    _default_prompt = 'You are a planner who is an expert at coming up with a todo list for a given objective. Come up with a todo list for this objective: {objective}'
    _default_description = 'useful for when you need to come up with todo lists. Input: an objective to create a todo list for. Output: a todo list for that objective. Please be very clear what the objective is!'

    for i, tool in enumerate(st.session_state['custom_tools']):
        with st.sidebar:
            with st.expander(f'Custom tool {i + 1}:', expanded=True):
                tool['name'] = st.text_input(
                    'Name:',
                    value=_default_name,
                    key=f'custom_tool_name_{i}',
                    help='Name of the tool.',
                    placeholder=_default_name,
                )
                tool['prompt'] = st.text_input(
                    'Prompt:',
                    value=_default_prompt,
                    key=f'custom_tool_prompt_{i}',
                    help='Prompt used for the tool.',
                    placeholder=_default_prompt,
                )
                tool['description'] = st.text_input(
                    'Description:',
                    value=_default_description,
                    key=f'custom_tool_description_{i}',
                    help='Add a description for the tool in a few words.',
                    placeholder=_default_description,
                )


update_predefined_tool_params()
update_custom_tools()


submit = st.button('Submit')


from pydantic import BaseModel, Field, ValidationError


class Response(BaseModel):
    result: str
    error: str
    stdout: str


class TaskDetails(BaseModel):
    id: str
    name: str


class HumanPrompt(BaseModel):
    prompt: str


async def talk_to_agent(
    objective: str,
    selected_params: Dict[str, Dict[str, str]],
):
    url = 'ws://localhost:8080'
    name = 'baby_agi'

    envs = {}
    tool_names = []
    for tool in selected_params.values():
        tool_names.append(tool['api'])
        for param, value in tool.items():
            if param != 'api':
                envs[param] = value
    tool_params = envs

    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(f'{url}/{name}') as ws:
            print(f'Connected to {url}/{name}.')
            await ws.send_json(
                {
                    "objective": objective,
                    'first_task': first_task,
                    "max_iterations": max_iterations,
                    'predefined_tools': {
                        'names': tool_names,
                        'params': tool_params,
                    },
                    'custom_tools': st.session_state['custom_tools'],
                    "envs": envs if envs else {},
                }
            )

            container = st.empty()
            block = ''
            added_table_in_last_iteration = False
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    if msg.data == 'close cmd':
                        await ws.close()
                        break
                    else:
                        try:
                            response = Response.parse_raw(msg.data)
                            if response.result:
                                text = response.result
                            if response.stdout:
                                text = response.stdout
                            if response.error:
                                text = response.error

                            if text:
                                print(f'Got response: "{text}"')
                                try:
                                    task = TaskDetails.parse_raw(text)
                                    table_header = (
                                        '| Task ID | Task Name | \n| :---: | :---: | \n'
                                    )
                                    if not added_table_in_last_iteration:
                                        block = f'{block}\n{table_header}'
                                        added_table_in_last_iteration = True

                                    block = f'{block}| {task.id} | {task.name} | \n'
                                    container.markdown(block)
                                    continue

                                except ValidationError:
                                    added_table_in_last_iteration = False
                                    if (
                                        'TASK LIST' in text
                                        or 'NEXT TASK' in text
                                        or 'TASK RESULT' in text
                                    ):
                                        text = f'\n--- \n##{text} \n\n'

                                    if 'TASK ENDING' in text:
                                        text = '\n--- \n'

                                    block = f'{block}\n{text}'
                                    container.write(block)
                        except ValidationError as e:
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


async def main():
    if submit:
        if not openai_token:
            st.error('Please enter your OpenAI token')
            return

        if not objective:
            st.error('Please enter your objective')
            return

        # if params are not provided for a tool, then don't run
        for tool in selected_tool_params:
            if len(ALL_TOOLS[tool]) > 0:
                for param in ALL_TOOLS[tool]['args']:
                    if not selected_tool_params[tool][param]:
                        st.error(f'Please enter `{param}` for tool `{tool}`')
                        return

        print(
            f'Running agent with objective: {objective} with params: {selected_tool_params}'
        )
        # with st.spinner(text="Running agent..."):
        await talk_to_agent(
            objective=objective,
            selected_params=selected_tool_params,
        )


if __name__ == '__main__':
    asyncio.run(main())
