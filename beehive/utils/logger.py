"""Logging configuration for Beehive."""

import logging
import sys
from pathlib import Path


def setup_logger(name: str = "beehive", level: int = logging.INFO) -> logging.Logger:
    """Set up and return a logger instance."""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    # Format
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)

    logger.addHandler(handler)
    return logger
