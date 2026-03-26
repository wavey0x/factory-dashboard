"""Structured logging setup."""

from __future__ import annotations

import logging
from enum import StrEnum

import structlog


class OutputMode(StrEnum):
    TEXT = "text"
    JSON = "json"


def configure_logging(*, verbose: bool = False, output_mode: OutputMode = OutputMode.JSON) -> None:
    """Configure stdlib + structlog for consistent scanner logs."""

    level = logging.DEBUG if verbose else logging.INFO
    if output_mode is OutputMode.TEXT and not verbose:
        level = logging.WARNING

    logging.basicConfig(
        format="%(message)s",
        level=level,
        force=True,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("tidal").setLevel(level)

    renderer = (
        structlog.dev.ConsoleRenderer()
        if output_mode is OutputMode.TEXT
        else structlog.processors.JSONRenderer()
    )

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.contextvars.merge_contextvars,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.stdlib.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
