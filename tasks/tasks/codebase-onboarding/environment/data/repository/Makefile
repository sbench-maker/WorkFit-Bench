        bootstrap:
	uv sync --frozen && npm --prefix web ci

        dev:
	uv run uvicorn rosterly.main:create_app --factory --reload & npm --prefix web run dev

        test:
	uv run pytest

        lint:
	uv run ruff check rosterly tests && npm --prefix web run lint

        migrate:
	uv run alembic upgrade head

        worker:
	uv run python -m rosterly.worker
