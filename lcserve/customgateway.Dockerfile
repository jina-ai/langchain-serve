FROM jinaai/jina:3.14.1-py310-standard

RUN apt-get update && apt-get install --no-install-recommends -y git pip nginx && rm -rf /var/lib/apt/lists/*

## install requirements for the gateway
COPY requirements.txt .
COPY agent-requirements.txt /agent-requirements.text
RUN pip install --compile -r requirements.txt -r agent-requirements.text

# setup the workspace
COPY . /workdir/
WORKDIR /workdir

# Rename customgateway_config.yml to config.yml
RUN mv customgateway_config.yml config.yml

ENTRYPOINT ["jina", "gateway", "--uses", "config.yml"]