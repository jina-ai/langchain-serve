ARG JINA_VERSION=latest

FROM jinaai/jina:${JINA_VERSION}-py310-standard

# install requirements before copying the workspace
COPY requirements.txt /requirements.txt
COPY agent-requirements.txt /agent-requirements.text
RUN pip install --default-timeout=1000 --compile -r requirements.txt -r agent-requirements.text

# setup the workspace
COPY . /workdir/
WORKDIR /workdir

ENTRYPOINT ["jina", "executor", "--uses", "/workdir/backend/agentexecutor_config.yml"