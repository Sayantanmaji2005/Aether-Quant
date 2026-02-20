# Contributing

## Setup

1. Create and activate a virtual environment.
2. Install dependencies with `pip install -e .[dev]`.
3. Copy `.env.example` to `.env` and adjust values for your environment.

## Quality checks

Run before opening a PR:

- `ruff check .`
- `mypy src`
- `pytest`

## Pull requests

- Keep PRs focused and small.
- Add or update tests for behavior changes.
- Include a short risk/rollback note in the PR description.

## Container workflow

- Build: `docker build -t aetherquant:latest .`
- Run: `docker compose up --build`
