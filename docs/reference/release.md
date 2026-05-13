# Release Process

Droplegen publishes to PyPI from GitHub Releases. The `Publish to PyPI` workflow builds the package with `uv build` and publishes with PyPI trusted publishing when a release is published.

## Preconditions

- `pyproject.toml` has the release version.
- `uv.lock` has been refreshed with `uv lock`.
- Tests, lint, package build, and a basic UI construction smoke check pass.
- PyPI trusted publishing is configured for this repository and the `publish.yml` workflow.

## Local Checks

```bash
uv run ruff check src tests
uv run pytest
uv build
```

## Commit And Tag

```bash
git status
git add pyproject.toml uv.lock README.md docs .github/workflows/publish.yml src
git commit -m "release 0.3.0"
git tag v0.3.0
git push origin master --follow-tags
```

## Publish

Create a GitHub Release for the pushed tag. Publishing the release triggers `.github/workflows/publish.yml`, which builds and publishes the package to PyPI.

With GitHub CLI:

```bash
gh release create v0.3.0 --title "v0.3.0" --notes "DropletUI 0.1.1 migration and UI cleanup."
```
