# Contributing to Garimpo

Thanks for helping. Start with [`README.md`](README.md) for what the project
does, and [`docs/quickstart.md`](docs/quickstart.md) to get from clone to first
alert.

## Setup

```bash
git clone https://github.com/LeoFabri1/garimpo.git
cd garimpo
uv sync
uv run garimpo --help
```

Optional Telegram backend (needed for live ingest):

```bash
uv sync --extra telethon
```

## Development checks

```bash
uv run ruff check src tests
uv run pytest
```

## Good first contributions (~15 min)

These three are where the project actually needs help, and each is small enough
to finish in one sitting:

1. **New group parser fixtures** — add 3 anonymized messages under
   `tests/fixtures/messages/<group>/`, run `pytest --snapshot-update`, open a PR.
2. **New GPU model** — edit `catalog/gpu.json`, run `garimpo catalog check`.
3. **New alert channel** — implement the `Channel` protocol in `alert/channels/`.

### Fixture rules

- Strip `@username`, affiliate links, phone numbers, and real names before commit.
- Run `garimpo fixtures-check` (also enforced in CI).

## Pull requests

- One focused change per PR when possible.
- Title should reflect the actual task.
- Link the related issue in the description.
- Do not commit `.env`, `*.session`, or `data/`.

## Publishing

Maintainers: see [`docs/publishing.md`](docs/publishing.md) for PyPI build and release.
