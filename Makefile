.PHONY: demo test lint build types migrate seed
demo:
	docker compose up --build -d
test:
	uv run pytest -q
	cd apps/web && npm test
lint:
	uv run ruff check services tests migrations
	cd apps/web && npm run lint
types:
	cd apps/web && npm run typecheck
build:
	cd apps/web && npm run build
migrate:
	uv run alembic upgrade head
seed:
	uv run python -m release_lab.seed
