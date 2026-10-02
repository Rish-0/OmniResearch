.PHONY: up down test lint typecheck migrate schemas install check

COMPOSE := docker compose -f infra/docker/compose.yml

up:
	$(COMPOSE) up -d --wait

down:
	$(COMPOSE) down

install:
	uv sync --all-packages
	cd apps/web && pnpm install

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run lint-imports

typecheck:
	uv run mypy packages/omni_contracts/src packages/omni_core/src packages/omni_db/src

test:
	uv run pytest tests/unit -x -v

test-integration:
	uv run pytest tests/integration -x -v -m integration

migrate:
	cd packages/omni_db && uv run alembic upgrade head

migrate-down:
	cd packages/omni_db && uv run alembic downgrade base

schemas:
	uv run python -m omni_contracts.export_schemas

check: lint typecheck test
	@echo "All checks passed!"
