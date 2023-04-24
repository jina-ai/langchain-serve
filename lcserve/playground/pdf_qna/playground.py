import os
import sys
import requests
import json

import streamlit as st
from pydantic import BaseModel


class Response(BaseModel):
    result: str
    error: str
    stdout: str


# get file dir and add it to sys.path
cwd = os.path.dirname(os.path.realpath(__file__))
sys.path.append(cwd)

st.set_page_config(
    page_title='Q&A Bot on PDFs',
    page_icon='⚡',
    layout='wide',
    initial_sidebar_state='auto',
)

st.sidebar.markdown('## OpenAI Token')
openai_token = st.sidebar.text_input(
    'Enter your OpenAI token:', placeholder='sk-...', type='password'
)


question = st.text_input(
    'Type your question',
    value='Kya iss scheme mai koi waiting period hai?',
    placeholder='Kya iss scheme mai koi waiting period hai?',
)


# allow to add multiple urls
urls = st.text_area(
    'Type your urls (separated by comma)',
    value='https://uiic.co.in/sites/default/files/uploads/downloadcenter/Arogya%20Sanjeevani%20Policy%20CIS_2.pdf',
    placeholder='https://uiic.co.in/sites/default/files/uploads/downloadcenter/Arogya%20Sanjeevani%20Policy%20CIS_2.pdf',
)

submit = st.button('Submit')


def main(host: str):
    if submit:
        if not openai_token:
            st.error('Please enter your OpenAI token')
            return

        if not question:
            st.error('Please enter your question')
            return

        headers = {'Content-Type': 'application/json'}
        data = {
            'urls': urls.split(','),
            'question': question,
            'envs': {'OPENAI_API_KEY': openai_token},
        }
        with st.spinner(text="Asking chain..."):
            response = requests.post(host, headers=headers, data=json.dumps(data))
            try:
                response = Response.parse_raw(response.text)
                st.write(response.result)
            except Exception as e:
                st.error(e)
                return


if __name__ == '__main__':
    # Get host from 1st arg
    host = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:8080/ask'
    main(host)
