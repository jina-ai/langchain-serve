def _ignore_warnings():
    import logging
    import warnings

    logging.captureWarnings(True)
    warnings.filterwarnings(
        "ignore",
        category=DeprecationWarning,
        message="Deprecated call to `pkg_resources.declare_namespace('google')`.",
    )


_ignore_warnings()

from .backend import serving, slackbot, download_df, upload_df
from .backend.slackbot.memory import MemoryMode, get_memory

__version__ = '0.0.47'
