default:
    @just --list

# Serve docs locally
docs-serve:
    uv run --group docs mkdocs serve

# Build docs
docs-build:
    uv run --group docs mkdocs build

# Deploy docs to GitHub Pages
docs-deploy:
    uv run --group docs mkdocs gh-deploy --force

# Run tests
test *args:
    uv run --group dev pytest {{ args }}

# Lint
lint:
    uv run --group dev ruff check src
    uv run --group dev ruff format --check src

# Format
fmt:
    uv run --group dev ruff check --fix src
    uv run --group dev ruff format src
