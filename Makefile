lint:
	ruff check .

test:
	pytest -q

dev:
	uvicorn apps.api.main:app --reload --host $${APP_HOST:-0.0.0.0} --port $${APP_PORT:-8000}
