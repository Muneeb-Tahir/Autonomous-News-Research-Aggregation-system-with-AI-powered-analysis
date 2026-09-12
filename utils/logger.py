"""
Logging configuration for the News Intelligence Agent.

Provides a consistent logger with formatted output.
Usage:
    from utils.logger import get_logger
    logger = get_logger(__name__)
    logger.info("Message")
"""

import logging
import sys
import io
from config.settings import LOG_LEVEL


def get_logger(name: str) -> logging.Logger:
    """Create a configured logger instance.

    Args:
        name: Logger name (typically __name__ of the calling module).

    Returns:
        Configured logging.Logger instance.
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))

        # Force UTF-8 output on Windows to avoid UnicodeEncodeError
        # when logging messages with emoji/unicode characters
        stream = io.TextIOWrapper(
            sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
        )
        handler = logging.StreamHandler(stream)
        handler.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))

        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger
