.PHONY: install dev test lint infra-up infra-down

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
