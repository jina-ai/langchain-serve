import asyncio
import inspect
import os
import shutil
import sys
import time
from enum import Enum
from functools import wraps
from importlib import import_module
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Tuple, Type, Union

from docarray import Document, DocumentArray
from jina import Gateway
from jina.enums import ProtocolType as GatewayProtocolType
from jina.logging.logger import JinaLogger
from jina.serve.runtimes.gateway.composite import CompositeGateway
from jina.serve.runtimes.gateway.http.fastapi import FastAPIBaseGateway
from pydantic import BaseModel, Field, ValidationError, create_model
from websockets.exceptions import ConnectionClosed

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
    run_function,
)
from .playground.utils.langchain_helper import (
    AsyncStreamingWebsocketCallbackHandler,
    BuiltinsWrapper,
    StreamingWebsocketCallbackHandler,
)

if TYPE_CHECKING:
    from fastapi import FastAPI
    from opentelemetry.sdk.metrics import Counter

cur_dir = os.path.dirname(__file__)


class RouteType(str, Enum):
    """RouteType is the type of route"""

    HTTP = 'http'
    WEBSOCKET = 'websocket'


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
        self._setup_metrics()

        self._register_healthz()
        for mod in modules:
            # TODO: add support for registering a directory
            if Path(mod).is_file() and mod.endswith('.py'):
                self._register_file(Path(mod))
            else:
                self._register_mod(mod)

    @property
    def app(self) -> 'FastAPI':
        return self._app

    def _fix_sys_path(self):
        if os.getcwd() not in sys.path:
            sys.path.append(os.getcwd())
        if Path(APPDIR).exists() and APPDIR not in sys.path:
            # This is where the app code is mounted in the container
            sys.path.append(APPDIR)

    def _setup_metrics(self):
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        if not self.meter_provider:
            self.http_duration_counter = None
            self.ws_duration_counter = None
            return

        FastAPIInstrumentor.instrument_app(
            self._app,
            meter_provider=self.meter_provider,
        )

        self.http_duration_counter = self.meter.create_counter(
            name="http_request_duration_seconds",
            description="HTTP request duration in seconds",
            unit="s",
        )

        self.ws_duration_counter = self.meter.create_counter(
            name="ws_request_duration_seconds",
            description="WS request duration in seconds",
            unit="s",
        )

    def _register_healthz(self):
        @self.app.get("/healthz")
        async def __healthz():
            return {'status': 'ok'}

        @self.app.get("/dry_run")
        async def __dry_run():
            return {'status': 'ok'}

    def _update_dry_run_with_ws(self):
        """Update the dry_run endpoint to a websocket endpoint"""
        from fastapi import WebSocket
        from fastapi.routing import APIRoute

        for route in self.app.routes:
            if route.path == '/dry_run' and isinstance(route, APIRoute):
                self.app.routes.remove(route)
                break

        @self.app.websocket("/dry_run")
        async def __dry_run(websocket: WebSocket):
            await websocket.accept()
            await websocket.send_json({'status': 'ok'})
            await websocket.close()

    def _register_mod(self, mod: str):
        try:
            app_module = import_module(mod)
            for _, func in inspect.getmembers(app_module, inspect.isfunction):
                self._register_func(func)
        except ModuleNotFoundError as e:
            import traceback

            traceback.print_exc()
            print(f'Unable to import module: {mod} as {e}')

    def _register_file(self, file: Path):
        try:
            spec = spec_from_file_location(file.stem, file)
            mod = module_from_spec(spec)
            spec.loader.exec_module(mod)
            for _, func in inspect.getmembers(mod, inspect.isfunction):
                self._register_func(func)
        except Exception as e:
            print(f'Unable to import {file}: {e}')

    def _register_func(self, func: Callable):
        def _get_decorator_params(func):
            if hasattr(func, '__serving__'):
                return getattr(func, '__serving__').get('params', {})
            elif hasattr(func, '__ws_serving__'):
                return getattr(func, '__ws_serving__').get('params', {})
            return {}

        _decorator_params = _get_decorator_params(func)
        if hasattr(func, '__serving__'):
            self._register_http_route(func, auth=_decorator_params.get('auth', None))
        elif hasattr(func, '__ws_serving__'):
            self._register_ws_route(
                func,
                auth=_decorator_params.get('auth', None),
                include_callback_handlers=_decorator_params.get(
                    'include_callback_handlers', False
                ),
            )

    def _register_http_route(self, func: Callable, auth: Callable = None, **kwargs):
        return self._register_route(
            func,
            auth=auth,
            route_type=RouteType.HTTP,
            **kwargs,
        )

    def _register_ws_route(
        self,
        func: Callable,
        auth: Callable = None,
        include_callback_handlers: bool = False,
        **kwargs,
    ):
        return self._register_route(
            func,
            auth=auth,
            route_type=RouteType.WEBSOCKET,
            include_callback_handlers=include_callback_handlers,
            **kwargs,
        )

    def _register_route(
        self,
        func: Callable,
        auth: Callable = None,
        route_type: RouteType = RouteType.HTTP,
        include_callback_handlers: bool = False,
        **kwargs,
    ):
        _name = func.__name__.title().replace('_', '')

        # check if _name is already registered
        if _name in [route.name for route in self.app.routes]:
            self.logger.debug(f'Route {_name} already registered. Skipping...')
            return

        class Config:
            arbitrary_types_allowed = True

        _input_fields, _file_fields = _get_input_model_fields(func)

        file_params = _get_file_field_params(_file_fields)
        input_model = create_model(
            f'Input{_name}',
            __config__=Config,
            **_input_fields,
            **{'envs': (Dict[str, str], Field(default={}, alias='envs'))},
        )

        output_model = create_model(
            f'Output{_name}',
            __config__=Config,
            **_get_output_model_fields(func),
        )

        if route_type == RouteType.HTTP:
            self.logger.info(f'Registering HTTP route: {func.__name__}')

            create_http_route(
                app=self.app,
                func=func,
                auth_func=auth,
                file_params=file_params,
                input_model=input_model,
                output_model=output_model,
                post_kwargs={
                    'path': f'/{func.__name__}',
                    'name': _name,
                    'description': func.__doc__ or '',
                    'tags': [SERVING],
                },
                logger=self.logger,
                duration_counter=self.http_duration_counter,
            )

        elif route_type == RouteType.WEBSOCKET:
            self.logger.info(f'Registering Websocket route: {func.__name__}')
            self._update_dry_run_with_ws()

            create_websocket_route(
                app=self.app,
                func=func,
                auth=auth,
                input_model=input_model,
                output_model=output_model,
                ws_kwargs={
                    'path': f'/{func.__name__}',
                    'name': _name,
                },
                include_callback_handlers=include_callback_handlers,
                logger=self.logger,
                duration_counter=self.ws_duration_counter,
            )


def _get_files_data(kwargs: Dict) -> Dict:
    from fastapi import UploadFile
    from starlette.datastructures import UploadFile as StarletteUploadFile

    _files_data = {}
    for k, v in kwargs.items():
        if isinstance(v, (UploadFile, StarletteUploadFile)):
            _files_data[k] = v

    return _files_data


def _get_func_data(
    func: Callable,
    input_data: Union[str, Dict, BaseModel],
    files_data: Dict,
    auth_response: Any = None,
    include_if_kwargs_exist: Dict = {},
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    import json

    if isinstance(input_data, BaseModel):
        _func_data = dict(input_data)
    elif isinstance(input_data, str):
        _func_data = json.loads(input_data)
    else:
        _func_data = input_data

    _envs = _func_data.pop('envs', {})

    if files_data:
        _func_data.update(files_data)

    # Read functions signature and check if `auth_response` is required or kwargs is present
    _func_params_names = list(inspect.signature(func).parameters.keys())
    if 'auth_response' in _func_params_names:
        _func_data['auth_response'] = auth_response
    elif 'kwargs' in _func_params_names:
        _func_data.update({'auth_response': auth_response})

    if include_if_kwargs_exist:
        _func_data.update(include_if_kwargs_exist)

    return _func_data, _envs


def _get_updated_signature(
    file_params: List[inspect.Parameter],
    output_model: BaseModel,
    include_token: bool = False,
) -> inspect.Signature:
    _params = [
        *file_params,
        inspect.Parameter(
            name='input_data',
            kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
            annotation=str,
        ),
    ]

    if include_token:
        _params.append(
            inspect.Parameter(
                name='token',
                kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=str,
            )
        )
    return inspect.Signature(parameters=_params, return_annotation=output_model)


def create_http_route(
    app: 'FastAPI',
    func: Callable,
    auth_func: Callable,
    file_params: List,
    input_model: BaseModel,
    output_model: BaseModel,
    post_kwargs: Dict,
    logger: JinaLogger,
    duration_counter: 'Counter',
):

    from fastapi import Depends, Form, HTTPException, Security, UploadFile, status
    from fastapi.encoders import jsonable_encoder
    from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

    bearer_scheme = HTTPBearer()

    async def _the_authorizer(
        credentials: HTTPAuthorizationCredentials = Security(bearer_scheme),
    ) -> Any:
        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token required"
            )

        try:
            auth_response = await run_function(auth_func, token=credentials.credentials)
        except Exception as e:
            logger.error(f'Could not verify token: {e}')
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bearer token"
            )

        return auth_response

    async def _the_route(
        input_data: input_model,
        files_data: Dict[str, UploadFile] = {},
        auth_response: Any = None,
    ) -> output_model:
        _output, _error = '', ''
        _func_data, _envs = _get_func_data(func, input_data, files_data, auth_response)
        with EnvironmentVarCtxtManager(_envs):
            with Capturing() as stdout:
                try:
                    _output = await run_function(func, **_func_data)
                except Exception as e:
                    logger.error(f'Got an exception: {e}')
                    _error = str(e)

            if _error != '':
                print(f'Error: {_error}')
            return output_model(
                result=_output,
                error=_error,
                stdout='\n'.join(stdout),
            )

    def _the_parser(data: str = Form(...)) -> input_model:
        try:
            model = input_model.parse_raw(data)
        except ValidationError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=jsonable_encoder(e.errors()),
            )

        return model

    if auth_func is not None:
        # If an auth function is present, we need to include the authorizer in the route.

        if len(file_params) > 0:
            # If file params are present, we need to use a custom parser to make sure that
            # the input data included in the Form and parsed correctly.

            @measure_duration(duration_counter)
            async def _the_http_route(
                input_data: input_model = Depends(_the_parser),
                auth_response: Any = Depends(_the_authorizer),
                **kwargs,
            ) -> output_model:
                return await _the_route(
                    input_data=input_data,
                    files_data=_get_files_data(kwargs),
                    auth_response=auth_response,
                )

            _the_http_route.__signature__ = _get_updated_signature(
                file_params, output_model, include_token=True
            )

        else:
            # If no file params are present, we include the input args in the Body.

            @measure_duration(duration_counter)
            async def _the_http_route(
                input_data: input_model, auth_response: Any = Depends(_the_authorizer)
            ) -> output_model:
                return await _the_route(
                    input_data=input_data,
                    files_data={},
                    auth_response=auth_response,
                )

    else:
        # If no auth function is present, no need to include the authorizer in the route.

        if len(file_params) > 0:
            # If file params are present, we need to use a custom parser to make sure that
            # the input data included in the Form and parsed correctly.

            @measure_duration(duration_counter)
            async def _the_http_route(
                input_data: input_model = Depends(_the_parser), **kwargs
            ) -> output_model:
                return await _the_route(
                    input_data=input_data,
                    files_data=_get_files_data(kwargs),
                    auth_response=None,
                )

            _the_http_route.__signature__ = _get_updated_signature(
                file_params, output_model, include_token=False
            )

        else:
            # If no file params are present, we include the input args in the Body.

            @measure_duration(duration_counter)
            async def _the_http_route(input_data: input_model) -> output_model:
                return await _the_route(
                    input_data=input_data,
                    files_data={},
                    auth_response=None,
                )

    # Add the route to the app with POST method
    app.post(**post_kwargs)(_the_http_route)


# TODO: add file upload support for websocket routes
def create_websocket_route(
    app: 'FastAPI',
    func: Callable,
    auth: Callable,
    input_model: BaseModel,
    output_model: BaseModel,
    include_callback_handlers: bool,
    ws_kwargs: Dict,
    logger: JinaLogger,
    duration_counter: 'Counter',
):
    from fastapi import (
        Depends,
        Header,
        WebSocket,
        WebSocketDisconnect,
        WebSocketException,
        status,
    )
    from fastapi.security.utils import get_authorization_scheme_param
    from fastapi.websockets import WebSocketState

    async def _the_authorizer(
        authorization: Union[str, None] = Header(None, alias="Authorization"),
    ) -> Any:
        scheme, token = get_authorization_scheme_param(authorization)
        if not (scheme and token):
            raise WebSocketException(
                code=status.WS_1008_POLICY_VIOLATION, reason="Not authenticated"
            )

        if scheme.lower() != "bearer":
            raise WebSocketException(
                code=status.WS_1008_POLICY_VIOLATION, reason="Unauthorized"
            )

        try:
            auth_response = await run_function(auth, token=token)
        except Exception as e:
            logger.error(f'Could not verify token: {e}')
            raise WebSocketException(
                code=status.WS_1008_POLICY_VIOLATION, reason="Invalid bearer token"
            )

        return auth_response

    async def _the_route(websocket: WebSocket, auth_response: Any = None):
        with BuiltinsWrapper(
            loop=asyncio.get_event_loop(),
            websocket=websocket,
            output_model=output_model,
            wrap_print=False,
        ):

            def _get_error_msg(e: Union[WebSocketDisconnect, ConnectionClosed]) -> str:
                return (
                    f'Client {websocket.client} disconnected from `{func.__name__}` with code {e.code}'
                    + (f' and reason {e.reason}' if e.reason else '')
                )

            await websocket.accept()
            _ws_recv_lock = asyncio.Lock()
            try:
                while True:
                    # if websocket is closed, break
                    if websocket.client_state not in [
                        WebSocketState.CONNECTED,
                        WebSocketState.CONNECTING,
                    ]:
                        logger.info(
                            f'Client {websocket.client} already disconnected from `{func.__name__}`. Breaking...'
                        )
                        break

                    async with _ws_recv_lock:
                        _data = await websocket.receive_json()

                    try:
                        _input_data = input_model(**_data)
                    except ValidationError as e:
                        logger.error(
                            f'Exception while converting data to input model: {e}'
                        )
                        _ws_serving_error = str(e)
                        _data = output_model(
                            result='',
                            error=_ws_serving_error,
                        )
                        await websocket.send_text(_data.json())
                        continue

                    _returned_data, _ws_serving_error = '', ''
                    # TODO: add support for file upload
                    _func_data, _envs = _get_func_data(
                        func=func,
                        input_data=_input_data,
                        files_data={},
                        auth_response=auth_response,
                        include_if_kwargs_exist={
                            'websocket': websocket,
                            'streaming_handler': StreamingWebsocketCallbackHandler(
                                websocket=websocket,
                                output_model=output_model,
                            ),
                            'async_streaming_handler': AsyncStreamingWebsocketCallbackHandler(
                                websocket=websocket,
                                output_model=output_model,
                            ),
                        }
                        if include_callback_handlers
                        else {},
                        # If the function is a streaming response, we pass the callback handler,
                        # so that stream data can be sent back to the client.
                    )
                    with EnvironmentVarCtxtManager(_envs):
                        try:
                            _returned_data = await run_function(func, **_func_data)
                            if inspect.isgenerator(_returned_data):
                                # If the function is a generator, we iterate through the generator and send each item back to the client.
                                for _stream in _returned_data:
                                    _data = output_model(
                                        result=_stream,
                                        error=_ws_serving_error,
                                    )
                                    await websocket.send_text(_data.json())

                            else:
                                # If the function is not a generator, we send the result back to the client.
                                _data = output_model(
                                    result=_returned_data,
                                    error=_ws_serving_error,
                                )
                                await websocket.send_text(_data.json())

                            # Once the generator is exhausted/ function call is completed, send a close message
                            logger.info(
                                f'Closing ws connection `{func.__name__}` for client: {websocket.client}'
                            )
                            await websocket.close()
                            break

                        except (WebSocketDisconnect, ConnectionClosed) as e:
                            logger.info(_get_error_msg(e))
                            break

                        except Exception as e:
                            logger.error(f'Got an exception: {e}', exc_info=True)
                            _ws_serving_error = str(e)
                            # For other errors, we send the error back to the client.
                            _data = output_model(
                                result='',
                                error=_ws_serving_error,
                            )
                            await websocket.send_text(_data.json())

                        if _ws_serving_error != '':
                            print(f'Error: {_ws_serving_error}')

            except (WebSocketDisconnect, ConnectionClosed) as e:
                logger.info(_get_error_msg(e))
                return

    if auth is not None:
        logger.info(f'Auth enabled for `{func.__name__}`')

        @app.websocket(**ws_kwargs)
        @measure_duration(duration_counter)
        async def _create_ws_route(
            websocket: WebSocket, auth_response: Any = Depends(_the_authorizer)
        ) -> output_model:
            return await _the_route(websocket=websocket, auth_response=auth_response)

    else:

        @app.websocket(**ws_kwargs)
        @measure_duration(duration_counter)
        async def _create_ws_route(websocket: WebSocket) -> output_model:
            return await _the_route(websocket=websocket, auth_response=None)


def _get_input_model_fields(
    func: Callable,
) -> Tuple[Dict[str, Tuple[Type, Any]], Dict[str, Tuple[Type, Any]]]:
    from fastapi import UploadFile

    _input_model_fields = {}
    _file_fields = {}

    for _name, _param in inspect.signature(func).parameters.items():
        if _param.kind == inspect.Parameter.VAR_KEYWORD:
            continue

        if _param.annotation is inspect.Parameter.empty:
            raise ValueError(
                f'Annotation missing for parameter {_name} in function {func.__name__}. '
                'Please add type annotations to all parameters.'
            )

        if _param.annotation == UploadFile:
            if _param.default is inspect.Parameter.empty:
                _file_fields[_name] = (_param.annotation, ...)
            else:
                _file_fields[_name] = (_param.annotation, _param.default)
        else:
            if _param.default is inspect.Parameter.empty:
                _input_model_fields[_name] = (_param.annotation, ...)
            else:
                _input_model_fields[_name] = (_param.annotation, _param.default)

    return _input_model_fields, _file_fields


def _get_file_field_params(
    fields: Dict[str, Tuple[Type, Any]]
) -> List[inspect.Parameter]:
    _file_field_params = []
    for _name, _field in fields.items():
        _file_field_params.append(
            inspect.Parameter(
                _name,
                inspect.Parameter.POSITIONAL_ONLY,
                annotation=_field[0],
                default=_field[1],
            )
        )
    return _file_field_params


def _get_output_model_fields(func: Callable) -> Dict[str, Tuple[Type, Any]]:
    def _get_result_type():
        if 'return' in func.__annotations__:
            _return = func.__annotations__['return']
            if hasattr(_return, '__next__'):  # if a Generator, return the first type
                return _return.__next__.__annotations__['return']
            elif _return is None:
                return str
            else:
                return _return
        else:
            return str

    _output_model_fields = {
        'result': (_get_result_type(), ...),
        'error': (str, ...),
        'stdout': (str, Field(default='', alias='stdout')),
    }

    return _output_model_fields


def measure_duration(duration_counter):
    class SharedData:
        def __init__(self, last_reported_time):
            self.last_reported_time = last_reported_time

    async def send_metrics_periodically(
        duration_counter, interval, route_name, shared_data
    ):
        while True:
            await asyncio.sleep(interval)
            current_time = time.perf_counter()
            if duration_counter:
                duration_counter.add(
                    current_time - shared_data.last_reported_time, {"route": route_name}
                )
            shared_data.last_reported_time = current_time

    def decorator(func):
        @wraps(func)
        async def wrapped(*args, **kwargs):
            shared_data = SharedData(last_reported_time=time.perf_counter())
            # Start the async task which reports the metrics every 5s
            send_metrics_task = asyncio.create_task(
                send_metrics_periodically(
                    duration_counter, 5, func.__name__, shared_data
                )
            )
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                send_metrics_task.cancel()
                # Final metrics update to wrap up the untracked duration in the end
                if duration_counter:
                    duration_counter.add(
                        time.perf_counter() - shared_data.last_reported_time,
                        {"route": func.__name__},
                    )

        return wrapped

    return decorator
