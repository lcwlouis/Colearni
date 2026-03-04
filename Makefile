lint:
	ruff check .

test:
	pytest -q

dev:
	uvicorn apps.api.main:app --reload --host $${APP_HOST:-0.0.0.0} --port $${APP_PORT:-8000}

serve:
	uvicorn apps.api.main:app --host $${APP_HOST:-0.0.0.0} --port $${APP_PORT:-8000} --workers $${APP_WORKERS:-4}

db-upgrade:
	alembic upgrade head

db-downgrade:
	alembic downgrade -1

db-revision:
	alembic revision -m "$${m}"

phoenix:
	docker compose --profile observability up -d phoenix

phoenix-down:
	docker compose --profile observability down

quiz-gardener:
	python -m apps.jobs.quiz_gardener

graph-gardener:
	python -m apps.jobs.graph_gardener

db-reset:
	python -m scripts.db_reset

db-reset-yes:
	python -m scripts.db_reset --yes
