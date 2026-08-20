# Security

## Reporting a vulnerability

Open a **private** security advisory on GitHub, or email the maintainer listed
on the repository. Do not file a public issue for leaked sessions, tokens, or
account-takeover risks.

## Userbot / ban risk

Garimpo logs in as a **user account** (MTProto), not a BotFather bot.

Telegram's [Content Licensing Terms](https://telegram.org/tos/content-licensing)
license data access to three categories — Client, Bot, Mini App. A read-only
daemon is none of them, so this falls *outside* the licensed exception rather
than into a grey area. **Restriction or ban of the phone number is a real
risk.** Always use a **secondary number**. See
[DISCLAIMER.md](DISCLAIMER.md) and
[docs/tos-compliance.md](docs/tos-compliance.md). The CLI `garimpo login` shows an
explicit banner and requires typing `secundario` before continuing.

Default backend is Telethon (`telegram.backend: telethon`). A Protocol-compatible
`pyrotgfork` backend is available (`uv sync --extra pyro`) if you need to migrate —
see [docs/hosting.md](docs/hosting.md).

## What is sensitive

| Item | Severity if leaked | What to do |
|------|--------------------|------------|
| `*.session` / `TG_SESSION` string | **Critical** — full Telegram account access | Revoke: Telegram → Settings → Devices → terminate the session. Rotate by logging in again. |
| `TG_BOT_TOKEN` | High | Revoke via BotFather (`/revoke`) and update env. |
| `TG_API_ID` / `TG_API_HASH` | Medium — identifies the *application*, not the account | Delete the app at https://my.telegram.org and create a new one. `api_hash` cannot be rotated in place. |

`api_id`/`api_hash` and the **session** are not the same class of secret. Treat
the session as the account itself.

## Hard rules for this repo

- Never commit `.env`, `data/`, or `*.session`.
- Prefer env var *names* in YAML (`token_env: TG_BOT_TOKEN`), never values.
- Use a **secondary phone number** for the userbot — never your primary
  account. The ban risk is real and it is the operator's.
- No AI: there is no LLM path, no provider key, nothing to leak there.

## Revoking access quickly

1. Telegram app → **Settings → Devices** → end the Garimpo / unknown session.
2. If a bot token leaked → BotFather → `/revoke`.
3. If `api_hash` leaked → delete the application on my.telegram.org.
