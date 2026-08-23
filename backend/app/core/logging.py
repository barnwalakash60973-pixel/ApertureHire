"""
Logging configuration. Uses stdlib logging with a consistent format so
logs are grep-able and, if piped through a JSON collector later, still
parseable by field.
"""

from __future__ import annotations

import logging
import sys

_CONFIGURED = False


def configure_logging(level: str = "INFO") -> None:
    """Configure root logging once per process. Safe to call repeatedly."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root = logging.getLogger()
    root.setLevel(level.upper())
    root.handlers = [handler]

    # Quiet noisy third-party loggers unless explicitly debugging.
    for noisy in ("httpx", "httpcore", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Get a module-scoped logger. Call configure_logging() first at startup."""
    return logging.getLogger(name)
