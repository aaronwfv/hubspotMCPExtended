"""
Logging configuration for HubSpot Extended MCP Server
"""

import logging
import sys
from typing import Any, Dict

import structlog


def configure_logging(log_level: str = "INFO") -> None:
    """Configure structured logging for the application."""

    # Configure standard library logging - use stderr to avoid interfering with MCP stdio
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=getattr(logging, log_level.upper()),
    )

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a configured logger instance."""
    return structlog.get_logger(name)