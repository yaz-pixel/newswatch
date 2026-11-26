.PHONY: setup lint format test migrate collect snapshot check-feeds

RUN = uv run --env-file .env python -m newswatch.main

setup:
	uv sync
	uv run pre-commit install

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff check --fix .
	uv run ruff format .

test:
	uv run pytest

migrate:
	$(RUN) migrate

collect:
	$(RUN) collect

snapshot:
	$(RUN) snapshot

check-feeds:
	$(RUN) check-feeds
