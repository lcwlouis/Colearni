from __future__ import annotations

import logging

_LOG_FORMAT = "%(levelname)s %(name)s %(message)s"
_LOG_LEVELS = {
    "critical": logging.CRITICAL,
    "error": logging.ERROR,
    "warning": logging.WARNING,
    "info": logging.INFO,
    "debug": logging.DEBUG,
}


def configure_logging(log_level: str) -> None:
    """Apply the configured log level to backend and uvicorn loggers.

    Uvicorn wires its own loggers, but it leaves application loggers without a
    handler by default. Add a root handler so backend log records are emitted.
    """
    level = _LOG_LEVELS.get(log_level.strip().lower(), logging.INFO)

    logging.getLogger("backend").setLevel(level)

    root_logger = logging.getLogger()
    if not root_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(_LOG_FORMAT))
        root_logger.addHandler(handler)

    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access", "uvicorn.asgi"):
        logging.getLogger(logger_name).setLevel(level)

    if level == logging.INFO and log_level.strip().lower() not in _LOG_LEVELS:
        logging.getLogger(__name__).warning(
            "Invalid LOG_LEVEL %r; defaulting to INFO",
            log_level,
        )
