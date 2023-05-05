from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pandas import DataFrame

import hubble


JINAAI_PREFIX = 'jinaai://'


def _import_pandas():
    try:
        import pandas as pd
    except ImportError:
        raise ImportError('Please install pandas using `pip install pandas`')
    return pd


def upload_df(df: 'DataFrame', name: str, to_csv_kwargs={}) -> str:
    with NamedTemporaryFile(suffix='.csv') as f:
        df.to_csv(f.name, **to_csv_kwargs)
        r = hubble.Client().upload_artifact(f=f.name, is_public=True, name=name)
        r.raise_for_status()
        id = r.json().get('data', {}).get('_id')
        if not id:
            raise ValueError('No id found in response')
        return JINAAI_PREFIX + id


def _download_df_from_jinaai(id: str, read_csv_kwargs={}) -> 'DataFrame':
    pd = _import_pandas()

    if not id.startswith(JINAAI_PREFIX):
        raise ValueError(f'Invalid id: {id}')
    id = id[len(JINAAI_PREFIX) :]

    with NamedTemporaryFile(suffix='.csv') as f:
        hubble.Client().download_artifact(id=id, f=f.name)
        return pd.read_csv(f.name, **read_csv_kwargs)


def download_df(id: str, read_csv_kwargs={}) -> 'DataFrame':
    pd = _import_pandas()

    if id.startswith(JINAAI_PREFIX):
        return _download_df_from_jinaai(id, read_csv_kwargs=read_csv_kwargs)
    else:
        df = pd.read_csv(id, **read_csv_kwargs)
        df.columns = [col.strip('" ') for col in df.columns]
        return df
