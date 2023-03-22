from collections import defaultdict
from typing import Any, Dict, List, Union

from pydantic import BaseModel

CLS = 'cls'
RESULT = 'result'
JINA_RESULTS = '__results__'
LLM_TYPE = '_type'
DEFAULT_FIELD = 'chain'
DEFAULT_KEY = '__default__'


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
