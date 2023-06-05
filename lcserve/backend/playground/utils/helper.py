import asyncio
import os
import subprocess
import sys
import threading
import importlib
import uuid
from collections import defaultdict
from io import StringIO
from typing import Any, Dict, List, Union, Callable, Tuple
import inspect
import functools

import nest_asyncio
from pydantic import BaseModel

CLS = 'cls'
RESULT = 'result'
LLM_TYPE = '_type'
DEFAULT_FIELD = 'chain'
DEFAULT_KEY = '__default__'
AGENT_OUTPUT = '__agent_output__'
SERVING = 'Serving'
APPDIR = '/appdir'

LANGCHAIN_API_PORT = os.environ.get('LANGCHAIN_API_PORT', 8080)
LANGCHAIN_PLAYGROUND_PORT = os.environ.get('LANGCHAIN_PLAYGROUND_PORT', 8501)


try:
    nest_asyncio.apply()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        nest_asyncio.apply()
    except RuntimeError:
        pass


def get_or_create_eventloop():
    try:
        return asyncio.get_event_loop()
    except RuntimeError as ex:
        if "There is no current event loop in thread" in str(ex):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return asyncio.get_event_loop()


def asyncio_run(func, *args, **kwargs):
    return get_or_create_eventloop().run_until_complete(func(*args, **kwargs))


def asyncio_run_property(func):
    task = asyncio.ensure_future(func)
    get_or_create_eventloop().run_until_complete(task)
    return task.result()


def parse_uses_with(uses_with: Union[Dict, BaseModel, List]) -> Dict[str, Any]:
    _uses_with = defaultdict(dict)

    def _parse(v):
        if isinstance(v, BaseModel):
            return {'cls': v.__class__.__name__, 'kwargs': v.dict(exclude_unset=True)}
        elif isinstance(v, type):
            return {'cls': v.__name__}
        elif isinstance(v, dict):
            return (
                {'cls': v['cls'], 'kwargs': v['kwargs']}
                if 'cls' in v
                else {kk: _parse(vv) for kk, vv in v.items()}
            )
        elif isinstance(v, list):
            return [_parse(vv) for vv in v]
        elif isinstance(v, (str, bool)):
            return v
        elif v is None:
            return v
        else:
            return v

    if isinstance(uses_with, BaseModel):
        uses_with = uses_with.dict()

    if isinstance(uses_with, dict):
        for k, v in uses_with.items():
            _uses_with[k] = _parse(v)
    elif isinstance(uses_with, list):
        for v in uses_with:
            _uses_with.update(_parse(v))

    return _uses_with


class Capturing(list):
    def __enter__(self, lock: threading.Lock = None):
        self._lock = lock
        if self._lock:
            self._lock.acquire()
        self._stdout = sys.stdout
        sys.stdout = self._stringio = StringIO()
        return self

    def __exit__(self, *args):
        self.extend(self._stringio.getvalue().splitlines())
        del self._stringio  # free up some memory
        sys.stdout = self._stdout
        if self._lock:
            self._lock.release()


class EnvironmentVarCtxtManager:
    """a class to wrap env vars"""

    def __init__(self, envs: Dict):
        """
        :param envs: a dictionary of environment variables
        """
        self._env_keys_added: Dict = envs
        self._env_keys_old: Dict = {}

    def __enter__(self):
        for key, val in self._env_keys_added.items():
            # Store the old value, if it exists
            if key in os.environ:
                self._env_keys_old[key] = os.environ[key]
            # Update the environment variable with the new value
            os.environ[key] = str(val)

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore the old values of updated environment variables
        for key, val in self._env_keys_old.items():
            os.environ[key] = str(val)
        # Remove any newly added environment variables
        for key in self._env_keys_added.keys():
            os.unsetenv(key)


class ChangeDirCtxtManager:
    """a class to wrap change dir"""

    def __init__(self, path: str):
        """
        :param path: a path to change
        """
        self._path = path
        self._old_path = None

    def __enter__(self):
        self._old_path = os.getcwd()
        os.chdir(self._path)

    def __exit__(self, exc_type, exc_val, exc_tb):
        os.chdir(self._old_path)


def run_cmd(command, std_output=False, wait=True):
    if isinstance(command, str):
        command = command.split()
    if not std_output:
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
    else:
        process = subprocess.Popen(command)
    if wait:
        output, error = process.communicate()
        return output, error


def get_random_tag():
    return 't-' + uuid.uuid4().hex[:5]


def get_random_name():
    return 'n-' + uuid.uuid4().hex[:5]


async def run_function(func: Callable, **kwargs):
    if inspect.iscoroutinefunction(func):
        return await func(**kwargs)
    else:
        return await asyncio.get_running_loop().run_in_executor(
            None,
            functools.partial(func, **kwargs),
        )


class ImportFromStringError(Exception):
    pass


def import_from_string(import_str: Any) -> Tuple[Any, Any]:
    if not isinstance(import_str, str):
        return import_str

    module_str, _, attrs_str = import_str.partition(":")
    if not module_str or not attrs_str:
        message = (
            'Import string "{import_str}" must be in format "<module>:<attribute>".'
        )
        raise ImportFromStringError(message.format(import_str=import_str))

    try:
        module = importlib.import_module(module_str)
    except ImportError as exc:
        if exc.name != module_str:
            raise exc from None
        message = 'Could not import module "{module_str}".'
        raise ImportFromStringError(message.format(module_str=module_str))

    app = module
    try:
        for attr_str in attrs_str.split("."):
            app = getattr(app, attr_str)
    except AttributeError:
        message = 'Attribute "{attrs_str}" not found in module "{module_str}".'
        raise ImportFromStringError(
            message.format(attrs_str=attrs_str, module_str=module_str)
        )

    return app, module
