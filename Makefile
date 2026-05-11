.PHONY: install dev test lint infra-up infra-down db-upgrade db-revision

install:
	pip install -e ".[dev]"

dev:
	uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest -q

lint:
	ruff check .

infra-up:
	docker compose up -d

infra-down:
	docker compose down

db-upgrade:
	alembic upgrade head

db-revision:
	alembic revision --autogenerate -m "$(m)"
