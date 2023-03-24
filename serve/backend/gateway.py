import os
import time
import shutil
from typing import Dict, List, Tuple

import streamlit.web.bootstrap
from fastapi import FastAPI, Query, Body
from docarray import Document, DocumentArray

from jina import Gateway
from jina.enums import GatewayProtocolType
from jina.serve.runtimes.gateway import CompositeGateway
from jina.serve.runtimes.gateway.http.fastapi import FastAPIBaseGateway

from streamlit.file_util import get_streamlit_file_path
from streamlit.web.server import Server as StreamlitServer

from .playground.utils.helper import (
    AGENT_OUTPUT,
    DEFAULT_KEY,
    RESULT,
    parse_uses_with,
    LANGCHAIN_PLAYGROUND_PORT,
    LANGCHAIN_API_PORT,
    run_cmd,
)

cur_dir = os.path.dirname(__file__)


class PlaygroundGateway(Gateway):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.streamlit_script = 'playground/app.py'
        # copy playground/config.toml to streamlit config.toml
        streamlit_config_toml_src = os.path.join(cur_dir, 'playground', 'config.toml')
        streamlit_config_toml_dest = get_streamlit_file_path("config.toml")
        # create streamlit_config_toml_dest if it doesn't exist
        os.makedirs(os.path.dirname(streamlit_config_toml_dest), exist_ok=True)
        shutil.copyfile(streamlit_config_toml_src, streamlit_config_toml_dest)

    async def setup_server(self):
        streamlit.web.bootstrap._fix_sys_path(self.streamlit_script)
        streamlit.web.bootstrap._fix_matplotlib_crash()
        streamlit.web.bootstrap._fix_tornado_crash()
        streamlit.web.bootstrap._fix_sys_argv(self.streamlit_script, ())
        streamlit.web.bootstrap._fix_pydeck_mapbox_api_warning()
        streamlit_cmd = f'streamlit run {self.streamlit_script}'

        self.streamlit_server = StreamlitServer(
            os.path.join(cur_dir, self.streamlit_script), streamlit_cmd
        )

    async def run_server(self):
        await self.streamlit_server.start()
        streamlit.web.bootstrap._on_server_start(self.streamlit_server)
        streamlit.web.bootstrap._set_up_signal_handler(self.streamlit_server)

    async def shutdown(self):
        self.streamlit_server.stop()


class LangchainFastAPIGateway(FastAPIBaseGateway):
    @property
    def app(self):
        app = FastAPI()

        @app.post("/run")
        async def __run(
            text: str = Query(default=..., description="The text to be processed"),
            parameters: Dict = Body(
                default=..., description="The parameters to be passed to the executor"
            ),
            envs: Dict = Body(
                default={},
                description="The environment variables to be passed to the executor",
            ),
            executor: str = Query(
                default="agent", description="The name of the executor"
            ),
            html: bool = Query(
                default=False,
                description="Whether to return the result as html or plain text",
            ),
        ):
            _parameters = parse_uses_with(parameters)
            if envs and 'env' in _parameters:
                _parameters['env'].update(envs)
            elif envs:
                _parameters['env'] = envs

            _parameters['html'] = html

            da = await self.executor[executor].post(
                on='/load_and_run',
                inputs=DocumentArray([Document(tags={DEFAULT_KEY: text})]),
                parameters=_parameters,
            )
            tags = da[0].tags
            if AGENT_OUTPUT in tags and RESULT in tags:
                return {
                    'result': tags[RESULT],
                    'chain_of_thought': ''.join(tags[AGENT_OUTPUT]),
                }
            elif RESULT in tags:
                return {'result': tags[RESULT]}
            else:
                return {'result': tags}

        return app


class LangchainAgentGateway(CompositeGateway):
    """The LangchainAgentGateway assumes that the gateway has been started with http on port 8081.
    This is the port on which the nginx process listens. After nginx has been started,
    it will start the playground on port 8501 and the API on port 8080. The actual
    HTTP gateway will start on port 8082.
    Nginx is configured to route the requests in the following way:
    - /playground -> playground on port 8501
    - /api -> API on port 8080
    - / -> HTTP gateway on port 8082
    """

    def __init__(self, **kwargs):
        # need to update port ot 8082, as nginx will listen on 8081
        http_idx = kwargs['runtime_args']['protocol'].index(GatewayProtocolType.HTTP)
        http_port = kwargs['runtime_args']['port'][http_idx]
        if kwargs['runtime_args']['port'][http_idx] != 8081:
            raise ValueError(
                f'Please, let http port ({http_port}) be 8081 for nginx to work'
            )

        kwargs['runtime_args']['port'][http_idx] = 8082
        super().__init__(**kwargs)

        # remove potential clashing arguments from kwargs
        kwargs.pop("port", None)
        kwargs.pop("protocol", None)

        # note order is important
        self._add_gateway(
            LangchainFastAPIGateway,
            LANGCHAIN_API_PORT,
            **kwargs,
        )
        self._add_gateway(
            PlaygroundGateway,
            LANGCHAIN_PLAYGROUND_PORT,
            **kwargs,
        )

        self.setup_nginx()
        self.nginx_was_shutdown = False

    async def shutdown(self):
        await super().shutdown()
        if not self.nginx_was_shutdown:
            self.shutdown_nginx()
            self.nginx_was_shutdown = True

    def setup_nginx(self):
        command = [
            'nginx',
            '-c',
            os.path.join(cur_dir, '', 'nginx.conf'),
        ]
        output, error = self._run_nginx_command(command)
        self.logger.info('Nginx started')
        self.logger.info(f'nginx output: {output}')
        self.logger.info(f'nginx error: {error}')

    def shutdown_nginx(self):
        command = ['nginx', '-s', 'stop']
        output, error = self._run_nginx_command(command)
        self.logger.info('Nginx stopped')
        self.logger.info(f'nginx output: {output}')
        self.logger.info(f'nginx error: {error}')

    def _run_nginx_command(self, command: List[str]) -> Tuple[bytes, bytes]:
        self.logger.info(f'Running command: {command}')
        output, error = run_cmd(command)
        if error != b'':
            # on CI we need to use sudo; using NOW_CI_RUN isn't good if running test locally
            self.logger.info(f'nginx error: {error}')
            command.insert(0, 'sudo')
            self.logger.info(f'So running command: {command}')
            output, error = run_cmd(command)
        time.sleep(10)
        return output, error

    def _add_gateway(self, gateway_cls, port, protocol='http', **kwargs):
        # ignore metrics_registry since it is not copyable
        runtime_args = self._deepcopy_with_ignore_attrs(
            self.runtime_args,
            [
                'metrics_registry',
                'tracer_provider',
                'grpc_tracing_server_interceptors',
                'aio_tracing_client_interceptors',
                'tracing_client_interceptor',
            ],
        )
        runtime_args.port = [port]
        runtime_args.protocol = [protocol]
        gateway_kwargs = {k: v for k, v in kwargs.items() if k != 'runtime_args'}
        gateway_kwargs['runtime_args'] = dict(vars(runtime_args))
        gateway = gateway_cls(**gateway_kwargs)
        gateway.streamer = self.streamer
        self.gateways.insert(0, gateway)
