# Contributing to Garimpo

Thanks for helping. The technical design lives in [`DESIGN-2.md`](DESIGN-2.md);
delivery cuts live in [`docs/SPRINTS.md`](docs/SPRINTS.md).

## Setup

```bash
git clone https://github.com/LeoFabri1/garimpo.git
cd garimpo
uv sync
uv run garimpo --help
```

Optional Telegram backend (needed from Sprint 3):

```bash
uv sync --extra telethon
```

## Development checks

```bash
uv run ruff check src tests
uv run pytest
```

## Good first contributions (~15 min)

See DESIGN §24.4 and the backlog in `docs/SPRINTS.md`:

1. **New group parser fixtures** — add 3 anonymized messages under
   `tests/fixtures/messages/<group>/`, run `pytest --snapshot-update`, open a PR.
2. **New GPU model** — edit `catalog/gpu.json`, run `garimpo catalog check` (when available).
3. **New alert channel** — implement the `Channel` protocol in `alert/channels/`.

### Fixture rules

- Strip `@username`, affiliate links, phone numbers, and real names before commit.
- CI will reject fixtures that look like affiliate URLs (when that check lands).

## Pull requests

- One focused change per PR when possible.
- Title should reflect the actual task.
- Link the related sprint/issue in the description.
- Do not commit `.env`, `*.session`, or `data/`.

## Publishing

Maintainers: see [`docs/publishing.md`](docs/publishing.md) for PyPI build and release.
