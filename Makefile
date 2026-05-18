.PHONY: install dev test lint infra-up infra-down db-upgrade db-revision

# Use uv if available; otherwise fall back to a plain .venv + pip.
UV := $(shell which uv 2>/dev/null)

ifdef UV
  RUN     := uv run
  install:
	uv sync --extra dev
else
  RUN     := .venv/bin/python -m
  install:
	python -m venv .venv && .venv/bin/pip install -e ".[dev]"
endif

dev:
	$(RUN) uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000

test:
	$(RUN) pytest -q

lint:
	$(RUN) ruff check .

infra-up:
	docker compose up -d

infra-down:
	docker compose down

db-upgrade:
	$(RUN) alembic upgrade head

db-revision:
	$(RUN) alembic revision --autogenerate -m "$(m)"
