.PHONY: dev test lint typecheck serve migrate format install frontend

install:
	uv sync --all-extras
	cd frontend && npm install

dev:
	cd frontend && npx concurrently \
		--names "api,web" \
		--prefix-colors "blue,green" \
		"cd .. && uv run uvicorn backend.main:app --reload --port 8000" \
		"npm run dev"

serve:
	uv run uvicorn backend.main:app --host 0.0.0.0 --port $${PORT:-8000}

test:
	uv run pytest

test-unit:
	uv run pytest tests/unit/

test-integration:
	uv run pytest tests/integration/

test-e2e:
	uv run pytest tests/e2e/

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff check --fix .
	uv run ruff format .

typecheck:
	uv run mypy backend/

migrate:
	uv run python -m backend.database

frontend:
	cd frontend && npm run build
