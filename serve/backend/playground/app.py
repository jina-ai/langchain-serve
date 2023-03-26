import streamlit as st
import os
import sys

# get file dir and add it to sys.path
cwd = os.path.dirname(os.path.realpath(__file__))
sys.path.append(cwd)

from utils.talk import talk_to_agent  # doesn't work
from utils.tools import ALL_TOOLS

st.sidebar.markdown('## OpenAI Token')
openai_token = st.sidebar.text_input(
    'Enter your OpenAI token:', placeholder='sk-...', type='password'
)

# Type your question
question = st.text_input(
    'Type your question:', placeholder='Who is Leo DiCaprio\'s girlfriend?'
)

selected_options = st.sidebar.multiselect('Select options:', ALL_TOOLS)
selected_params = {}

for option in selected_options:
    api = ALL_TOOLS[option]['api']
    selected_params[option] = {}
    selected_params[option]['api'] = api

    if len(ALL_TOOLS[option]['args']) > 0:
        st.sidebar.write(f'`{option}` parameters:')

        for param in ALL_TOOLS[option]['args']:
            param_value = st.sidebar.text_input(
                'label',
                key=f'{option}_{param}',
                label_visibility='collapsed',
                placeholder=param,
                type='password',
            )
            selected_params[option][param] = param_value

submit = st.button('Submit')


def main():
    if submit:
        if not openai_token:
            st.error('Please enter your OpenAI token')
            return

        if not question:
            st.error('Please enter your question')
            return

        if not selected_options:
            st.error('Please select at least one option')
            return

        # if params are not provided for a tool, then don't run
        for option in selected_options:
            if len(ALL_TOOLS[option]) > 0:
                for param in ALL_TOOLS[option]['args']:
                    if not selected_params[option][param]:
                        st.error(f'Please enter `{param}` for `{option}`')
                        return

        with st.spinner(text="Running agent..."):
            result, chain_of_thought = talk_to_agent(
                inputs=question,
                parameters=selected_params,
                openai_token=openai_token,
            )

        st.write(result)

        # Optionally show the chain of thought, if user expands the subsection
        with st.expander('See chain of thought'):
            st.write(chain_of_thought, unsafe_allow_html=True)


if __name__ == '__main__':
    main()
