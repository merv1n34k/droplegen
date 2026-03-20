.PHONY: setup dev build test test-all lint fmt clean docs-dev docs-build

setup:
	@test -d fgt-SDK || git clone https://github.com/Fluigent/fgt-SDK.git fgt-SDK
	uv sync

dev:
	uv run python -m droplegen

build:
	uv build

test:
	uv run pytest tests/unit

test-all:
	uv run pytest

lint:
	uv run ruff check .

fmt:
	uv run ruff format .

clean:
	rm -rf dist/ .pytest_cache/ __pycache__/ .ruff_cache/ *.egg-info/

docs-dev:
	cd docs && bun run docs:dev

docs-build:
	cd docs && bun run docs:build
