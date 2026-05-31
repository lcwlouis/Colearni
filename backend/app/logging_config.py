from __future__ import annotations

import logging
import os

_LOG_FORMAT = "%(asctime)s.%(msecs)03d | %(levelname)s | %(shortname)s | %(message)s"
_LOG_DATE_FORMAT = "%H:%M:%S"
_LOG_LEVELS = {
    "critical": logging.CRITICAL,
    "error": logging.ERROR,
    "warning": logging.WARNING,
    "info": logging.INFO,
    "debug": logging.DEBUG,
}
_RESET = "\x1b[0m"
_DIM = "\x1b[2m"
_LOGGER_COLOR = "\x1b[36m"
_LEVEL_COLORS = {
    logging.DEBUG: "\x1b[34m",
    logging.INFO: "\x1b[32m",
    logging.WARNING: "\x1b[33m",
    logging.ERROR: "\x1b[31m",
    logging.CRITICAL: "\x1b[35;1m",
}


def _short_logger_name(name: str) -> str:
    if name.startswith("backend.app."):
        return name.removeprefix("backend.app.")
    if name.startswith("backend."):
        return name.removeprefix("backend.")
    return name


def _supports_color(stream: object | None) -> bool:
    if os.getenv("NO_COLOR"):
        return False
    if os.getenv("FORCE_COLOR"):
        return True
    if stream is None or not hasattr(stream, "isatty"):
        return False

    try:
        return bool(stream.isatty())
    except Exception:
        return False


class _TerminalFormatter(logging.Formatter):
    def __init__(self, *, use_color: bool) -> None:
        super().__init__(_LOG_FORMAT, datefmt=_LOG_DATE_FORMAT)
        self._use_color = use_color

    def format(self, record: logging.LogRecord) -> str:
        original_levelname = record.levelname
        original_shortname = getattr(record, "shortname", None)

        level_label = f"{original_levelname:<8}"
        logger_name = _short_logger_name(record.name)

        if self._use_color:
            color = _LEVEL_COLORS.get(record.levelno, "")
            record.levelname = f"{color}{level_label}{_RESET}" if color else level_label
            record.shortname = f"{_LOGGER_COLOR}{logger_name}{_RESET}"
        else:
            record.levelname = level_label
            record.shortname = logger_name

        try:
            rendered = super().format(record)
        finally:
            record.levelname = original_levelname
            if original_shortname is None:
                delattr(record, "shortname")
            else:
                record.shortname = original_shortname

        if not self._use_color:
            return rendered

        timestamp, separator, rest = rendered.partition(" | ")
        if not separator:
            return rendered
        return f"{_DIM}{timestamp}{_RESET}{separator}{rest}"


def _build_formatter(*, use_color: bool) -> logging.Formatter:
    return _TerminalFormatter(use_color=use_color)


def _configure_handlers(logger: logging.Logger, level: int) -> None:
    for handler in logger.handlers:
        handler.setLevel(level)
        use_color = _supports_color(getattr(handler, "stream", None))
        handler.setFormatter(_build_formatter(use_color=use_color))


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
        root_logger.addHandler(handler)

    _configure_handlers(root_logger, level)

    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access", "uvicorn.asgi"):
        logger = logging.getLogger(logger_name)
        logger.setLevel(level)
        _configure_handlers(logger, level)

    if level == logging.INFO and log_level.strip().lower() not in _LOG_LEVELS:
        logging.getLogger(__name__).warning(
            "Invalid LOG_LEVEL %r; defaulting to INFO",
            log_level,
        )
