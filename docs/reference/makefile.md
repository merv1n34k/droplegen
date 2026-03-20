# Makefile Targets

All project operations are accessible through `make` targets.

## Core Targets

| Target | Command | Description |
|--------|---------|-------------|
| `make setup` | `uv sync` | Install all dependencies |
| `make dev` | `uv run python -m droplegen` | Launch the GUI application |
| `make build` | `uv build` | Build distributable package |
| `make test` | `uv run pytest tests/unit` | Run unit tests |
| `make test-all` | `uv run pytest` | Run all tests (unit + integration) |
| `make lint` | `uv run ruff check .` | Check code style |
| `make fmt` | `uv run ruff format .` | Auto-format code |
| `make clean` | `rm -rf dist/ ...` | Remove build artifacts and caches |

## Documentation Targets

| Target | Command | Description |
|--------|---------|-------------|
| `make docs-dev` | `cd docs && bun run docs:dev` | Start docs dev server |
| `make docs-build` | `cd docs && bun run docs:build` | Build static docs site |

### Documentation Setup

Before using docs targets, install dependencies:

```bash
cd docs && bun install
```

The docs site uses [VitePress](https://vitepress.dev/) and is located in the `docs/` directory.
