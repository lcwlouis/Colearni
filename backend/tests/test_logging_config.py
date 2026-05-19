from __future__ import annotations

import logging

from backend.app.logging_config import configure_logging


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

        assert "debug logging works" in captured.err
        assert "backend.app.services.workspaces" in captured.err
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
