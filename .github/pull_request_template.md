<!--
  Pre-alpha personal experiment. PRs may sit unanswered or be closed without
  merging — see CONTRIBUTING.md before spending time on a large change.
-->

## What and why

<!-- What changes, and what problem it solves. -->

## Checks

- [ ] `uv run pytest`
- [ ] `uv run ruff check src/ tests/`
- [ ] `uv run garimpo fixtures-check` — no affiliate links, shorteners, handles
      or phone numbers in fixtures or tests
- [ ] No `.env`, `*.session`, `data/` or any secret value in the diff

## Scope

- [ ] Does not collect people (member lists, contacts, profiles, presence)
- [ ] Does not write to monitored groups (post, react, mark read, auto-join)
- [ ] Adds no AI/LLM path, no monetization, no anti-bot evasion

<!-- These are declined regardless of implementation quality. CONTRIBUTING.md
     explains why each one changes what the project is. -->
