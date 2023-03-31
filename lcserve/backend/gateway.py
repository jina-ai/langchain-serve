import inspect
import os
import shutil
import sys
import time
from importlib import import_module
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Callable, Dict, List, Tuple

from docarray import Document, DocumentArray
from jina import Gateway
from jina.enums import GatewayProtocolType
from jina.serve.runtimes.gateway import CompositeGateway
from jina.serve.runtimes.gateway.http.fastapi import FastAPIBaseGateway
from pydantic import create_model

from .playground.utils.helper import (
    AGENT_OUTPUT,
    APPDIR,
    DEFAULT_KEY,
    LANGCHAIN_API_PORT,
    LANGCHAIN_PLAYGROUND_PORT,
    RESULT,
    SERVING,
    Capturing,
    EnvironmentVarCtxtManager,
    parse_uses_with,
    run_cmd,
)

cur_dir = os.path.dirname(__file__)


class PlaygroundGateway(Gateway):
    def __init__(self, **kwargs):
        from streamlit.file_util import get_streamlit_file_path

        super().__init__(**kwargs)
        self.streamlit_script = 'playground/app.py'
        # copy playground/config.toml to streamlit config.toml
        streamlit_config_toml_src = os.path.join(cur_dir, 'playground', 'config.toml')
        streamlit_config_toml_dest = get_streamlit_file_path("config.toml")
        # create streamlit_config_toml_dest if it doesn't exist
        os.makedirs(os.path.dirname(streamlit_config_toml_dest), exist_ok=True)
        shutil.copyfile(streamlit_config_toml_src, streamlit_config_toml_dest)

    async def setup_server(self):
        import streamlit.web.bootstrap
        from streamlit.web.server import Server as StreamlitServer

        streamlit.web.bootstrap._fix_sys_path(self.streamlit_script)
        streamlit.web.bootstrap._fix_sys_path(os.path.join(cur_dir, 'playground'))
        streamlit.web.bootstrap._fix_matplotlib_crash()
        streamlit.web.bootstrap._fix_tornado_crash()
        streamlit.web.bootstrap._fix_sys_argv(self.streamlit_script, ())
        streamlit.web.bootstrap._fix_pydeck_mapbox_api_warning()
        streamlit_cmd = f'streamlit run {self.streamlit_script}'
        self.streamlit_server = StreamlitServer(
            os.path.join(cur_dir, self.streamlit_script), streamlit_cmd
        )

    async def run_server(self):
        import streamlit.web.bootstrap

        await self.streamlit_server.start()
        streamlit.web.bootstrap._on_server_start(self.streamlit_server)
        streamlit.web.bootstrap._set_up_signal_handler(self.streamlit_server)

    async def shutdown(self):
        self.streamlit_server.stop()


class LangchainFastAPIGateway(FastAPIBaseGateway):
    @property
    def app(self):
        from fastapi import Body, FastAPI

        app = FastAPI()

        @app.post("/run")
        async def __run(
            text: str = Body(
                default=...,
                description="The text to be processed",
            ),
            parameters: Dict = Body(
                default=..., description="The parameters to be passed to the executor"
            ),
            envs: Dict = Body(
                default={},
                description="The environment variables to be passed to the executor",
            ),
            executor: str = Body(
                default="agent",
                description="The name of the executor",
            ),
            html: bool = Body(
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

        @app.get("/healthz")
        async def __healthz():
            return {'status': 'ok'}

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
        runtime_args = kwargs['runtime_args']
        runtime_args['metrics_registry'] = None
        runtime_args['tracer_provider'] = None
        runtime_args['grpc_tracing_server_interceptors'] = None
        runtime_args['aio_tracing_client_interceptors'] = None
        runtime_args['tracing_client_interceptor'] = None
        kwargs['runtime_args'] = runtime_args
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


class ServingGateway(FastAPIBaseGateway):
    def __init__(self, modules: Tuple[str] = (), *args, **kwargs):
        from fastapi import FastAPI

        super().__init__(*args, **kwargs)
        self.logger.debug(f'Loading modules/files: {",".join(modules)}')
        self._fix_sys_path()
        self._app = FastAPI()
        self._register_healthz()
        for mod in modules:
            # TODO: add support for registering a directory
            if Path(mod).is_file() and mod.endswith('.py'):
                self._register_file(Path(mod))
            else:
                self._register_mod(mod)

    @property
    def app(self):
        return self._app

    def _fix_sys_path(self):
        if os.getcwd() not in sys.path:
            sys.path.append(os.getcwd())
        if Path(APPDIR).exists() and APPDIR not in sys.path:
            # This is where the app code is mounted in the container
            sys.path.append(APPDIR)

    def _register_healthz(self):
        @self._app.get("/healthz")
        async def __healthz():
            return {'status': 'ok'}

        @self._app.get("/dry_run")
        async def __dry_run():
            return {'status': 'ok'}

    def _register_mod(self, mod: str):
        try:
            app_module = import_module(mod)
            for name, func in inspect.getmembers(app_module, inspect.isfunction):
                if getattr(func, '__serving__', False):
                    self._register_route(func)
        except ModuleNotFoundError:
            print(f'Unable to import module: {mod}')

    def _register_file(self, file: Path):
        try:
            spec = spec_from_file_location(file.stem, file)
            mod = module_from_spec(spec)
            spec.loader.exec_module(mod)

            for name, func in inspect.getmembers(mod, inspect.isfunction):
                if getattr(func, '__serving__', False):
                    self._register_route(func)
        except Exception as e:
            print(f'Unable to import {file}: {e}')

    def _register_route(self, func: Callable, **kwargs):
        _name = func.__name__.title().replace('_', '')

        # check if _name is already registered
        if _name in [route.name for route in self.app.routes]:
            print(f'Route {_name} already registered. Skipping...')
            return

        _input_params = [
            (name, parameter.annotation)
            for name, parameter in inspect.signature(func).parameters.items()
        ]

        _input_model_fields = {
            name: (field_type, ...) for name, field_type in _input_params
        }
        _output_model_fields = {
            'result': (
                func.__annotations__['return']
                if 'return' in func.__annotations__
                else str,
                ...,
            ),
            'error': (str, ...),
            'stdout': (str, ...),
        }

        class Config:
            arbitrary_types_allowed = True

        input_model = create_model(
            f'Input{_name}',
            __config__=Config,
            **_input_model_fields,
            **{'envs': (Dict[str, str], ...)},
        )

        output_model = create_model(
            f'Output{_name}',
            __config__=Config,
            **_output_model_fields,
        )

        @self.app.post(
            path=f'/{func.__name__}',
            name=_name,
            description=func.__doc__ or '',
            tags=[SERVING],
        )
        async def _create_route(input_data: input_model) -> output_model:
            output, error = '', ''
            envs = {}
            if hasattr(input_data, 'envs'):
                envs = input_data.envs
                del input_data.envs

            with EnvironmentVarCtxtManager(envs):
                with Capturing() as stdout:
                    try:
                        output = func(**dict(input_data))
                    except Exception as e:
                        print(f'Got an exception: {e}')
                        error = str(e)

                if error != '':
                    print(f'Error: {error}')
                return output_model(
                    result=output,
                    error=error,
                    stdout='\n'.join(stdout),
                )
