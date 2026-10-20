"""Shared logging configuration for CLI and server entry points."""

import logging

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"

# Noisy third-party loggers silenced unless verbose.
_QUIET_LOGGERS = ["httpx", "uvicorn.access", "playwright"]


def configure_logging(verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format=LOG_FORMAT,
    )
    if not verbose:
        for name in _QUIET_LOGGERS:
            logging.getLogger(name).setLevel(logging.WARNING)
