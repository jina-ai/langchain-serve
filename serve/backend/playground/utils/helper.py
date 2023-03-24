import os
import threading
import subprocess
from collections import defaultdict
from typing import Any, Dict, List, Union

from pydantic import BaseModel

CLS = 'cls'
RESULT = 'result'
LLM_TYPE = '_type'
DEFAULT_FIELD = 'chain'
DEFAULT_KEY = '__default__'
AGENT_OUTPUT = '__agent_output__'

LANGCHAIN_API_PORT = os.environ.get('LANGCHAIN_API_PORT', 8080)
LANGCHAIN_PLAYGROUND_PORT = os.environ.get('LANGCHAIN_PLAYGROUND_PORT', 8501)

import sys
from io import StringIO


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
