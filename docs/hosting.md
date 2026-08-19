# Deploy templates — honest about cost (DESIGN §21)

Garimpo needs a **24/7 host** with persistent disk for `data/` (DB + session).

## Recommended

**VPS ~€4/mês** (Hetzner CX22 / DigitalOcean basic) or a Raspberry Pi you already own.

Do **not** run on a laptop that sleeps — holes in price history corrupt scoring.

## Docker

```bash
cp config/quickstart.yaml config/config.yaml
# set alerts.channel, sources, .env
docker compose up -d --build
```

Volume `./data` is **mandatory**. Without it, session/DB die on recreate and you
hit FloodWait login loops.

## systemd

See [`garimpo.service`](../garimpo.service) — install under `/etc/systemd/system/`.

## Heartbeat (strongly recommended)

Silent death looks like “no good deals”. Ping Healthchecks.io / Uptime Kuma:

```yaml
health:
  heartbeat_url_env: HEARTBEAT_URL
  interval_minutes: 5
```

```bash
# .env
HEARTBEAT_URL=https://hc-ping.com/your-uuid
```

## Platform templates

| File | Notes |
|------|--------|
| [`deploy/fly.toml`](../deploy/fly.toml) | Needs volume; costs money |
| [`deploy/railway.json`](../deploy/railway.json) | Use `TG_SESSION` on ephemeral disk |
| [`deploy/render.yaml`](../deploy/render.yaml) | Free tier sleeps — useless for daemon |

README must not promise “run for free”.

## Backup

```bash
sqlite3 data/garimpo.db ".backup /backup/garimpo-$(date +%F).db"
```

Weekly cron. The DB is the asset.
