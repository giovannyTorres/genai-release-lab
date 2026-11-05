.PHONY: demo quickcheck test lint build types migrate seed
demo:
	docker compose up --build -d --wait
quickcheck:
	TEST_DATABASE_URL= uv run --frozen pytest -q \
		tests/test_domain.py::test_fixture_regression_is_calculated \
		tests/test_domain.py::test_full_persistent_gate_export_and_approval \
		tests/test_domain.py::test_regression_rejected_and_mandatory_llm_pending \
		tests/test_domain.py::test_cli_exit_codes \
		tests/test_audit.py::test_cli_hash_covers_rules_and_invalid_input_exit
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
