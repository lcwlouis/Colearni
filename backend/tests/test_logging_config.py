from __future__ import annotations

from io import StringIO
import logging
import re

from backend.app.logging_config import configure_logging


class _TTYBuffer(StringIO):
    def isatty(self) -> bool:
        return True


def test_configure_logging_emits_backend_debug_logs(capsys):
    root_logger = logging.getLogger()
    backend_logger = logging.getLogger("backend")
    uvicorn_loggers = {
        name: logging.getLogger(name)
        for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "uvicorn.asgi")
    }

    original_root_handlers = list(root_logger.handlers)
    original_root_level = root_logger.level
    original_backend_level = backend_logger.level
    original_uvicorn_levels = {name: logger.level for name, logger in uvicorn_loggers.items()}

    try:
        for handler in list(root_logger.handlers):
            root_logger.removeHandler(handler)

        root_logger.setLevel(logging.WARNING)
        backend_logger.setLevel(logging.NOTSET)
        for logger in uvicorn_loggers.values():
            logger.setLevel(logging.INFO)

        configure_logging("debug")
        logging.getLogger("backend.app.services.workspaces").debug("debug logging works")

        captured = capsys.readouterr()
        log_line = captured.err.strip()

        assert "\x1b[" not in log_line
        assert re.search(
            r"\d{2}:\d{2}:\d{2}\.\d{3} \| DEBUG\s+\| services\.workspaces \| debug logging works",
            log_line,
        )
        assert backend_logger.level == logging.DEBUG
        assert all(logger.level == logging.DEBUG for logger in uvicorn_loggers.values())
    finally:
        for handler in list(root_logger.handlers):
            root_logger.removeHandler(handler)

        for handler in original_root_handlers:
            root_logger.addHandler(handler)

        root_logger.setLevel(original_root_level)
        backend_logger.setLevel(original_backend_level)
        for name, logger in uvicorn_loggers.items():
            logger.setLevel(original_uvicorn_levels[name])


def test_configure_logging_reformats_existing_root_handlers(capsys):
    root_logger = logging.getLogger()
    backend_logger = logging.getLogger("backend")

    original_root_handlers = list(root_logger.handlers)
    original_root_level = root_logger.level
    original_backend_level = backend_logger.level

    try:
        for handler in list(root_logger.handlers):
            root_logger.removeHandler(handler)

        existing_handler = logging.StreamHandler()
        existing_handler.setLevel(logging.WARNING)
        existing_handler.setFormatter(logging.Formatter("%(message)s"))
        root_logger.addHandler(existing_handler)

        backend_logger.setLevel(logging.NOTSET)

        configure_logging("debug")
        logging.getLogger("backend.app.services.workspaces").debug("existing handler updated")

        captured = capsys.readouterr()
        log_line = captured.err.strip()

        assert "\x1b[" not in log_line
        assert re.search(
            r"\d{2}:\d{2}:\d{2}\.\d{3} \| DEBUG\s+\| services\.workspaces \| existing handler updated",
            log_line,
        )
    finally:
        for handler in list(root_logger.handlers):
            root_logger.removeHandler(handler)

        for handler in original_root_handlers:
            root_logger.addHandler(handler)

        root_logger.setLevel(original_root_level)
        backend_logger.setLevel(original_backend_level)


def test_configure_logging_uses_colors_for_tty_handlers():
    root_logger = logging.getLogger()
    backend_logger = logging.getLogger("backend")

    original_root_handlers = list(root_logger.handlers)
    original_root_level = root_logger.level
    original_backend_level = backend_logger.level

    try:
        for handler in list(root_logger.handlers):
            root_logger.removeHandler(handler)

        tty_stream = _TTYBuffer()
        root_logger.addHandler(logging.StreamHandler(tty_stream))
        backend_logger.setLevel(logging.NOTSET)

        configure_logging("info")
        logging.getLogger("backend.app.services.workspaces").info("tty color works")

        log_line = tty_stream.getvalue().strip()

        assert "\x1b[" in log_line

        plain_log_line = re.sub(r"\x1b\[[0-9;]*m", "", log_line)
        assert re.search(
            r"\d{2}:\d{2}:\d{2}\.\d{3} \| INFO\s+\| services\.workspaces \| tty color works",
            plain_log_line,
        )
    finally:
        for handler in list(root_logger.handlers):
            root_logger.removeHandler(handler)

        for handler in original_root_handlers:
            root_logger.addHandler(handler)

        root_logger.setLevel(original_root_level)
        backend_logger.setLevel(original_backend_level)
