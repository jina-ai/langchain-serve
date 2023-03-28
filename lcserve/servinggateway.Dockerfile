FROM jinaai/jina:3.14.1-py310-standard

RUN apt-get update && apt-get install --no-install-recommends -y git pip nginx && rm -rf /var/lib/apt/lists/*

# setup the workspace
COPY . /workdir/
WORKDIR /workdir

RUN pip install -e . && \
    pip install --compile -r requirements.txt -r lcserve/requirements.txt

# Rename servinggateway_config.yml to config.yml
RUN mv lcserve/servinggateway_config.yml config.yml && cp config.yml lcserve/config.yml

ENTRYPOINT ["jina", "gateway", "--uses", "config.yml"]