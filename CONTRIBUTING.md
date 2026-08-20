# Contributing to Garimpo

**Set expectations first.** This is a pre-alpha personal experiment with no
support and no compatibility promise. Interfaces, schema and behaviour change
without notice, and issues or pull requests may go unanswered for a long time
or be closed without merging. Nobody is on call here.

That is not a brush-off — it is the honest version, so you can decide whether
to spend your time. Read [DISCLAIMER.md](DISCLAIMER.md) before anything else;
it covers the ban risk and what the project deliberately does not do.

If you still want to poke at it: [`README.md`](README.md) for what it does,
[`docs/quickstart.md`](docs/quickstart.md) to get from clone to first alert.

## Out of scope

Some things will be declined regardless of how well they are implemented,
because they change what the project is:

- **Anything that collects people.** Member lists, contacts, profiles, presence.
  The project never calls `GetParticipants` and that is deliberate.
- **Anything that writes to the monitored groups.** Posting, reacting, marking
  as read, auto-joining.
- **AI or LLM features.** Removed on purpose — see
  [docs/tos-compliance.md](docs/tos-compliance.md) §2.
- **Monetization.** Affiliate links, commissions, sponsored placement. It makes
  the use economic, biases the recommendation toward whoever pays, and removes
  the LGPD art. 4º, I exemption the project relies on.
- **Evading anti-bot protection** on retailer sites — headless browsers,
  captcha solvers, residential proxies. See [docs/baseline.md](docs/baseline.md).

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

## Where help is actually useful

If you want to contribute anyway, these are small and unlikely to be wasted:

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

## Not published to PyPI

Deliberately. Shipping this as `pip install` makes it easy to run for someone
who never read the ban warning, and a published version cannot be recalled.
[`docs/publishing.md`](docs/publishing.md) documents the suspended release
flow.
