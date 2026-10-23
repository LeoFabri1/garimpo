# Garimpo

A Python tool that monitors Telegram deal channels, keeps price history in
SQLite, and alerts you when an offer matches your price and statistical rules.

Garimpo uses regular expressions, a curated product catalog, and historical
price statistics. It does not use AI or require an LLM API key. Live monitoring
does require your own Telegram application credentials.

*Garimpo* is Portuguese for prospecting: sifting through gravel to find a nugget.

**Status:** pre-alpha personal project. Interfaces and behavior may change;
there is no support or compatibility guarantee. The project is not published
to PyPI. Install from this repository.

[Try it offline](#try-it-offline) · [Connect Telegram](#connect-telegram) ·
[Alert delivery](#choose-where-alerts-go) · [Run continuously](#run-continuously) ·
[Troubleshooting](#troubleshooting)

## What it does

- Parses product names, prices, stores, coupons, and links from deal messages.
- Matches offers against GPU, CPU, notebook, and RAM catalogs and your watch rules.
- Stores messages, offers, price observations, and alert decisions in SQLite.
- Computes a weighted historical median, median absolute deviation (MAD), and
  percentile ranks, with configurable history windows and recency weighting.
- Delivers alerts to the terminal, Telegram Saved Messages, a Telegram bot, or
  a webhook, with cooldowns, rate limits, and quiet hours.
- Includes Telegram backfill, GPU offer simulation, CSV export, a local price
  panel, and an optional MCP server.

### How a price becomes an alert

```text
Telegram message -> product/price parsing -> watch-rule filters
                 -> historical price comparison -> alert delivery
```

The default scoring window is 90 days, with a 21-day half-life and a minimum
of 12 observations. Prices are compared with offers collected from your
configured sources, not with the entire retail market.

**A short history is not evidence of an exceptional deal.** Until enough
observations exist, eligible offers under your price ceiling can receive a
normal alert marked as low confidence. See [baseline limitations](docs/baseline.md).

<a id="aviso--leia-antes-de-fazer-login"></a>

## Before connecting to Telegram

Garimpo reads through a **Telegram user account using MTProto**, not through
a BotFather bot. The optional bot is only an alert delivery channel.

**Use a secondary account and phone number.** Automated account access carries
a risk of restriction or suspension. Garimpo does not join groups, collect
member lists, post to monitored groups, react, or mark messages as read.

Read the [disclaimer](DISCLAIMER.md), [security guidance](SECURITY.md), and
[project notes on Telegram's terms](docs/tos-compliance.md) before logging in.
Review the [Telegram API terms](https://core.telegram.org/api/terms) and
[content licensing terms](https://telegram.org/tos/content-licensing) for your
intended use. Garimpo does not implement sponsored-message support.

The CLI asks you to type `secundario` (Portuguese for “secondary”) before login.
Some CLI messages and supporting documents are still in Portuguese.

## Try it offline

You need **Git**, **Python 3.12 or newer**, and
[uv](https://docs.astral.sh/uv/getting-started/installation/).
If needed, [install Python with uv](https://docs.astral.sh/uv/guides/install-python/).
The shell examples below use Bash/Zsh syntax.

```bash
git clone https://github.com/LeoFabri1/garimpo.git
cd garimpo
uv sync --python 3.12

uv run garimpo run --dry-run -c config/quickstart.yaml \
  -m 'RTX 5070 Ti ASUS - R$ 5.799 no PIX Kabum'
```

This processes a sample Brazilian-real offer without connecting to Telegram
or sending notifications. The output includes the processing status and alert
level. **Dry runs use an in-memory database**: they do not add sample prices
to your saved history, so a later `stats` command will not count this example.

For the available commands:

```bash
uv run garimpo --help
uv run garimpo run --help
```

## Connect Telegram

Run commands from the repository root so Garimpo can find `.env`, configuration,
and relative data paths. Keep one live process per Telegram session file.

### 1. Install the Telegram extra and create local configuration

```bash
uv sync --extra telethon
cp .env.example .env
cp config/quickstart.yaml config/config.yaml
```

These copy commands are for a fresh setup; keep your existing files if you
have already configured Garimpo.

Obtain your application credentials from
[my.telegram.org](https://my.telegram.org), then fill in `.env`:

```dotenv
TG_API_ID=YOUR_NUMERIC_API_ID
TG_API_HASH=YOUR_32_CHARACTER_API_HASH
```

Never commit `.env`, Telegram session files, database files, or personal
configuration backups. The session file grants access to the authenticated account.

### 2. Set your sources and products

Replace the contents of `config/config.yaml` with this minimal configuration,
then replace the channel placeholder with a channel your secondary account
can access:

```yaml
sources:
  - "@your_deals_channel"

watch:
  - name: gpu-watch
    category: gpu
    models: ["RTX 5070 Ti", "RX 9070 XT"]
    max_price: 6000

alerts:
  channel: console

storage:
  path: data/garimpo.db
```

`max_price` is a ceiling in BRL, not a suggested market price. Set it for the
products you want to monitor. Model names must resolve to the curated catalog;
`doctor` reports names it cannot find. Private groups require the account to
already be a member; use a numeric `id` entry when needed.

See [config/config.example.yaml](config/config.example.yaml) for more categories,
numeric source IDs, quiet hours, per-rule overrides, webhooks, and Bark sirens.
It is a reference configuration, not a list of current buying recommendations.

### 3. Log in and check the setup

```bash
uv run garimpo login --qr
uv run garimpo doctor
```

Scan the QR code using the Telegram app signed into your secondary account.
For code-based login or two-factor authentication, see [login options](docs/login.md).
With `channel: console`, eligible alerts appear in the terminal only.

### 4. Import recent history before starting the listener

```bash
uv run garimpo backfill --telegram --days 30
uv run garimpo stats
uv run garimpo simulate --days 30
```

Backfill imports recent messages into the local database **without sending
alerts**. Use it before the first live run: `run --once` is a gap-recovery pass,
not a replacement for recent-history backfill. On a fresh database it can
start from the oldest messages in a channel.

`simulate` reports alert-level counts for stored GPU offers under the current
rules. It does not send alerts or reproduce delivery cooldowns and rate limits.

### 5. Start monitoring

```bash
uv run garimpo run
```

Leave the process running; press **Ctrl+C** to stop. Choose a phone delivery
channel below if you want notifications outside the terminal.

## Choose where alerts go

Edit the existing `alerts` block in `config/config.yaml`; do not add a second
block with the same key.

| Channel | Configuration | Additional setup |
| --- | --- | --- |
| Terminal | `channel: console` | None; no phone notifications |
| Saved Messages | `channel: saved_messages` | Uses the secondary account's session |
| Telegram bot | `channel: bot` | `TG_BOT_TOKEN` and `TG_CHAT_ID` in `.env` |
| Webhook | `channel: webhook` | `WEBHOOK_URL` in `.env` |

### Send bot alerts to your main Telegram account

The secondary account still reads the channels; the bot delivers alerts to
the account that starts a conversation with it.

1. Create a bot through [BotFather](https://core.telegram.org/bots/tutorial#obtain-your-bot-token)
   and save its token as `TG_BOT_TOKEN` in `.env`.
2. From the account that should receive alerts, open your bot and send `/start`.
3. Read `message.chat.id` from the bot's
   [getUpdates response](https://core.telegram.org/bots/api#getupdates) and save
   it as `TG_CHAT_ID`. The snippet below loads your token from `.env` and prints
   private chat IDs without printing the token:

```bash
uv run python - <<'PY'
import os
import httpx
from garimpo.auth.login import load_dotenv_if_present

load_dotenv_if_present()
token = os.environ["TG_BOT_TOKEN"]
data = httpx.get(
    f"https://api.telegram.org/bot{token}/getUpdates", timeout=15
).json()
if not data.get("ok"):
    raise SystemExit(data.get("description", "Bot API request failed"))
for update in data["result"]:
    chat = update.get("message", {}).get("chat", {})
    if chat.get("type") == "private":
        print(chat["id"])
PY
```

If it prints nothing, send a new message to your bot and retry. Choose the ID
for your intended recipient if multiple private chats appear.

4. Set `alerts.channel: bot`, run `uv run garimpo doctor`, and restart the
   listener. A bot token does not replace `TG_API_ID`, `TG_API_HASH`, or login.

Restart a running listener after changing configuration or `.env`.

## Run continuously

For continuous monitoring, use a machine that stays online with persistent
storage for `data/`. Sleeping or disconnecting pauses ingestion; recovery can
fill gaps, but continuous availability provides more timely alerts.

### macOS

After configuring and logging in, stop any foreground listener, then use:

```bash
uv run garimpo daemon start
uv run garimpo daemon status
uv run garimpo daemon logs -f
```

`start` generates a LaunchAgent with the paths for your machine. After changing
settings, use `uv run garimpo daemon restart`. To stop background monitoring,
use `uv run garimpo daemon stop`.

### Linux and Docker

Use the [systemd service template](garimpo.service), adapting its user and
absolute paths, or the [Docker hosting guide](docs/hosting.md). Complete login
and backfill first. Docker must retain the `data/` volume to preserve the
database and session. The `daemon` subcommands currently support macOS only.

## Useful commands

| Command | Purpose |
| --- | --- |
| `uv run garimpo doctor --quick` | Check local setup without probing the Telegram session |
| `uv run garimpo stats` | Inspect stored message, offer, and history counts |
| `uv run garimpo simulate --days 30` | Preview score levels for stored GPU offers |
| `uv run garimpo panel` | Open a read-only price panel at `http://127.0.0.1:8765` |
| `uv run garimpo export --out data/prices.csv` | Export price history to CSV |
| `uv run garimpo catalog check` | Validate catalog structure and aliases |
| `uv run garimpo logout` | Revoke the Telegram session and remove its local file |

The panel command starts a local server; open the URL in your browser. Keep
it bound to localhost unless you provide your own access controls.

An optional MCP server exposes local queries for offers, history, and alerts:

```bash
uv sync --extra telethon --extra mcp
uv run garimpo mcp
```

`mcp` uses standard input/output for an MCP client. It uses `data/garimpo.db`
by default; set `GARIMPO_DB` to query another database.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| `uv` is not found | Install uv and reopen your terminal. |
| Telegram backend is missing | Run `uv sync --extra telethon` again. |
| No sources are configured | Replace the channel placeholder in `config/config.yaml`; the quickstart intentionally has no sources. |
| A source cannot be resolved | Check its username/ID and whether the secondary account can access it; run `doctor` with the listener stopped. |
| `database is locked` during session checks | Avoid sharing a session between processes. Use `doctor --quick`, or stop the listener before a full check. |
| Messages arrive but there are no alerts | Check product aliases, category, price ceiling, history size, cooldowns, and rate limits. `console` never sends phone notifications. |
| A notification arrives without sound | Normal alerts are silent by default; check `alerts.normal.silent`, rule overrides, and phone notification settings. |
| `stats` is empty after the offline example | Expected: dry runs do not persist data. Use backfill for actual history. |

The catalog and parser patterns are curated, not universal. The `condition`
watch filter and automatic MAD-based outlier exclusion are not wired into
the scoring path yet; see the notes in the full example configuration.

## Further reading

| Document | Contents |
| --- | --- |
| [Full configuration example](config/config.example.yaml) | Available settings and implementation notes |
| [Login](docs/login.md) | QR/code authentication, sessions, and revocation |
| [Hosting](docs/hosting.md) | Docker, systemd, persistent storage, and backups |
| [Baseline](docs/baseline.md) | Historical sampling bias and statistical limitations |
| [Telegram terms notes](docs/tos-compliance.md) | Current limitations and open questions |
| [Security](SECURITY.md) | Credential handling and incident response |
| [Disclaimer](DISCLAIMER.md) | Project scope and account risks |
| [Contributing](CONTRIBUTING.md) | Development setup and checks |

## License

[MIT](LICENSE).
