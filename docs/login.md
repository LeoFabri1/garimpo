# Login Telegram (api_id / api_hash / QR)

## Risco de ban e posição frente ao ToS (obrigatório ler)

O Garimpo é um **userbot**: autentica como conta de usuário via MTProto e lê
grupos.

### Onde isso cai no ToS

Os [Content Licensing Terms](https://telegram.org/tos/content-licensing)
concedem acesso a dados numa base "limited, non-exclusive, non-transferable
[...] solely to the extent strictly required" para operar um **Telegram
Client**, um **Telegram Bot** ou um **Telegram Mini App**. É uma lista fechada,
e o Garimpo não está nela.

Pontos concretos a considerar:

- A concessão é explícita e enumera três categorias. O Garimpo não se
  apresenta como nenhuma delas, então não conte com essa licença para cobrir
  o seu uso — avalie por conta própria.
- **[API ToS §3.3](https://core.telegram.org/api/terms):** quem acessa conteúdo
  de canais deve suportar sponsored messages. O Garimpo não implementa esse
  suporte; um daemon sem interface não tem onde exibi-las.
- **Cláusula de AI:** os mesmos termos proíbem "scraping, indexing, harvesting,
  aggregation or use of data [...] to train, fine-tune, validate or otherwise
  engage in the development, enhancement, benchmarking or deployment of
  artificial intelligence, machine learning models". O `llm.enabled` manda
  texto de mensagem para um LLM externo — por isso vem desligado.

Use por sua conta e risco. Análise completa e o que dá para mudar no código:
[docs/tos-compliance.md](tos-compliance.md).

### Mitigação prática

- Existe **risco real** de restrição ou **banimento do número** da sessão.
- Use **número secundário**. Nunca o Telegram principal.
- No `garimpo login`, um banner aparece e você precisa digitar `secundario`
  para continuar (ou `--i-understand` em automação — o risco continua o mesmo).

O cliente **não** envia mensagens nos grupos monitorados, não reage, não marca
como lido e **não lista membros** (`GetParticipants` é o padrão que o Telegram
pune mais agressivamente — o Garimpo não o usa). Escrita é só para você
(Saved Messages / bot próprio).

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

## Logout / revogar

```bash
uv run garimpo logout
```

Revoga a sessão **no servidor** do Telegram e só então apaga o arquivo local —
o dispositivo desaparece de Configurações → Dispositivos.

Apagar `data/session.session` na mão **não** revoga nada: a sessão continua
autorizada e quem tiver uma cópia do arquivo segue lendo sua conta. Se você já
apagou o arquivo, revogue pelo app em Configurações → Dispositivos.

`--local-only` existe para o caso de você não ter mais rede/credenciais, e
avisa explicitamente que a sessão segue ativa.

## Session string (hosts efêmeros)

```bash
uv run garimpo login --qr --export-string
# guarde em TG_SESSION — nunca commite
```

A string é acesso total à conta. Revogue em Dispositivos se vazar.

## Segurança

- `data/*.session` está no `.gitignore`
- Detalhes: [SECURITY.md](../SECURITY.md)
