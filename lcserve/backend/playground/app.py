import os
import sys

import streamlit as st

# get file dir and add it to sys.path
cwd = os.path.dirname(os.path.realpath(__file__))
sys.path.append(cwd)

from utils.talk import talk_to_agent  # doesn't work
from utils.tools import ALL_AGENT_TYPES, ALL_TOOLS

st.set_page_config(
    page_title='Langchain on Jina',
    page_icon='⚡',
    layout='wide',
    initial_sidebar_state='auto',
)

st.sidebar.markdown('## OpenAI Token')
openai_token = st.sidebar.text_input(
    'Enter your OpenAI token:', placeholder='sk-...', type='password'
)

agent_type = st.sidebar.selectbox(
    'Select agent type:', list(ALL_AGENT_TYPES.keys()), index=0
)

# Type your question
question = st.text_input(
    'Type your question:', placeholder='Who is Leo DiCaprio\'s girlfriend?'
)


selected_tools = st.sidebar.multiselect('Select tools:', ALL_TOOLS)
selected_params = {}

for tool in selected_tools:
    api = ALL_TOOLS[tool]['api']
    selected_params[tool] = {}
    selected_params[tool]['api'] = api

    if len(ALL_TOOLS[tool]['args']) > 0:
        st.sidebar.write(f'`{tool}` parameters:')

        for param in ALL_TOOLS[tool]['args']:
            param_value = st.sidebar.text_input(
                'label',
                key=f'{tool}_{param}',
                label_visibility='collapsed',
                placeholder=param,
                type='password',
            )
            selected_params[tool][param] = param_value

submit = st.button('Submit')


def main():
    if submit:
        if not openai_token:
            st.error('Please enter your OpenAI token')
            return

        if not question:
            st.error('Please enter your question')
            return

        if not selected_tools:
            st.error('Please select at least one option')
            return

        # if params are not provided for a tool, then don't run
        for tool in selected_tools:
            if len(ALL_TOOLS[tool]) > 0:
                for param in ALL_TOOLS[tool]['args']:
                    if not selected_params[tool][param]:
                        st.error(f'Please enter `{param}` for `{tool}`')
                        return

        with st.spinner(text="Running agent..."):
            result, chain_of_thought = talk_to_agent(
                question=question,
                selected_params=selected_params,
                agent_type=ALL_AGENT_TYPES[agent_type],
                openai_token=openai_token,
            )

        st.write(result)

        # Optionally show the chain of thought, if user expands the subsection
        with st.expander('See chain of thought'):
            st.write(chain_of_thought, unsafe_allow_html=True)


if __name__ == '__main__':
    main()
