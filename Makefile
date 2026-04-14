.PHONY: install sync dev test run

install:
	uv sync --dev

sync:
	uv sync --dev

dev:
	uv run python run.py

run:
	uv run python run.py

test:
	uv run pytest -v
