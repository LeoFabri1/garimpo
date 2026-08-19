# Login Telegram (api_id / api_hash / QR)

## Risco de ban (obrigatório ler)

O Garimpo é um **userbot**: autentica como conta de usuário via MTProto e lê
grupos. Isso é **zona cinza no ToS do Telegram**.

- Existe **risco real** de restrição ou **banimento do número** da sessão.
- Use **número secundário**. Nunca o Telegram principal.
- No `garimpo login`, um banner aparece e você precisa digitar `secundario`
  para continuar (ou `--i-understand` em automação — o risco continua o mesmo).

O cliente **não** envia mensagens nos grupos monitorados, não reage e não marca
como lido. Escrita é só para você (Saved Messages / bot próprio).

---

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

1. Leia o aviso de ban e digite `secundario`
2. Escaneie o QR: Telegram → **Configurações → Dispositivos → Conectar dispositivo**
3. Contas com 2FA: `--password`

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

- `data/*.session` está no `.gitignore`
- Detalhes: [SECURITY.md](../SECURITY.md)
