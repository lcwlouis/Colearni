lint:
	ruff check .

test:
	pytest -q

dev:
	uvicorn apps.api.main:app --reload --host $${APP_HOST:-0.0.0.0} --port $${APP_PORT:-8000}

db-upgrade:
	alembic upgrade head

db-downgrade:
	alembic downgrade -1

db-revision:
	alembic revision -m "$${m}"
