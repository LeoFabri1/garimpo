# Login Telegram (api_id / api_hash / QR)

Passo a passo completo do DESIGN §20. Resumo operacional:

## 1. Criar aplicação

1. Entre em https://my.telegram.org e faça login com o **número secundário**
2. **API Development tools** → crie um app (App title + Short name)
3. Copie `api_id` (número) e `api_hash` (32 hex)

O `api_hash` **não pode ser revogado** — se vazar, delete o app e crie outro.

## 2. Configurar

```bash
cp .env.example .env
# edite TG_API_ID e TG_API_HASH
cp config/quickstart.yaml config/config.yaml
uv sync --extra telethon
```

## 3. Login (QR — recomendado)

```bash
uv run garimpo login --qr
```

No app Telegram: **Configurações → Dispositivos → Conectar dispositivo** e
escaneie o QR. Contas com 2FA pedem senha (`--password`).

Após ~3 falhas o comando **aborta** de propósito (FloodWait de ~22h no Telegram).

## 4. Conferir

```bash
uv run garimpo doctor
uv run garimpo run --once
```

## Session string (hosts efêmeros)

```bash
uv run garimpo login --qr --export-string
# guarde em TG_SESSION — nunca commite
```

A string é acesso total à conta. Revogue em Dispositivos se vazar.

## Segurança

- Use número **secundário**, nunca o principal (risco de ban — userbot)
- `data/*.session` está no `.gitignore`
- Detalhes: [SECURITY.md](../SECURITY.md) · DESIGN §20 / §22
