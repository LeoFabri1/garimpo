# Quickstart — do clone ao primeiro alerta

## Offline (sem Telegram)

```bash
git clone https://github.com/LeoFabri1/garimpo.git
cd garimpo
uv sync
uv run garimpo run --dry-run -c config/quickstart.yaml \
  -m 'RTX 5070 Ti ASUS — R$ 5.799 no PIX Kabum'
```

## Com Telegram (número secundário)

1. Leia o [aviso de risco de ban](../README.md#aviso--leia-antes-de-fazer-login)
2. `api_id` / `api_hash` em https://my.telegram.org — ver [login.md](login.md)
3. Configure e autentique:

```bash
uv sync --extra telethon
cp .env.example .env
cp config/quickstart.yaml config/config.yaml
# edite sources: para grupos que a conta secundária já participa
# alerts.channel: saved_messages   # padrão recomendado na v0.1

uv run garimpo login --qr    # digite: secundario
uv run garimpo doctor
uv run garimpo run --once    # ou: garimpo run
```

Alerta aparece no terminal (`console`) ou em **Mensagens Salvas** se
`alerts.channel: saved_messages`.

## Sem API key de LLM

Não há caminho de IA no projeto — nenhuma chave de API é necessária,
nem opcional.
