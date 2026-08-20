# Primeira execução: o que o usuário enfrenta hoje

Documento de trabalho. Levanta a distância entre o que o CLI oferece e o que
foi preciso fazer à mão para tirar o projeto do zero até o primeiro alerta
legítimo (sessão de 2026-08-19/20, 7 fontes, 13.622 mensagens).

Nada aqui está implementado.

---

## 1. O caminho real, hoje

O quickstart cobre até `run --dry-run`. Do dry-run até um daemon útil, foi
preciso escrever **quatro scripts avulsos**, nenhum deles no repo:

1. Descobrir o `msg_id` da última mensagem de cada canal e semear
   `sources.last_msg_id`, senão a ingestão começa pelo **início do grupo** —
   no nosso caso, novembro de 2020.
2. Um laço chamando `recover_source(limit=1000, alert=False)` até esgotar,
   porque `run --once` avança só 200 por passada e um canal ativo tem 177 mil
   mensagens.
3. SQL para ver o funil, porque `stats` não mostra `triaged_out` nem taxa de
   parse.
4. SQL para contar amostras por modelo e saber se algum passou de
   `min_samples=12`, que é a condição para o score sequer ligar.

Um usuário final não vai escrever nada disso. E o pior: **sem o passo 1 o
produto parece funcionar** — ele ingere, parseia, não alerta, e a pessoa
conclui que não presta, quando na verdade está lendo preço de placa de vídeo
de cinco anos atrás.

## 2. Por que isso acontece

A causa raiz é o `ingest/recovery.py` ser gap recovery, não backfill. Com
`last_msg_id = 0` e `reverse=True`, `fetch_since` pede as mensagens **mais
antigas**:

```python
min_id = get_last_msg_id(pipeline.conn, resolved.tg_id)   # 0 na primeira vez
messages = await client.fetch_since(resolved, min_id=min_id, limit=limit)
```

Isso está correto para retomar um daemon que caiu. É exatamente errado para
começar. As duas situações usam o mesmo caminho, e só uma foi projetada.

---

## 3. `doctor` deve resolver as fontes contra o Telegram

**Custo:** baixo.

Hoje (`tools/doctor.py:130`) o check só conta entradas do YAML:

```
✓ sources — 7: @iskandarsouza, @ofertasadrenaline, ...
```

Isso passa com username inexistente, com canal do qual a conta não é membro e
com typo. A falha só aparece em `run`, como um warning no meio do log, e
`resolve_sources` segue adiante com as que sobraram — o usuário fica com menos
fontes do que pediu sem perceber.

### Desenho

Resolver cada fonte via `client.resolve_source` quando houver sessão, e
reportar por linha: resolvida (com o `tg_id`), não resolvida (com o motivo), e
a data da última mensagem — que responde de graça "esse canal ainda está
vivo?". Sem sessão, degradar para o check atual e dizer que não validou.

### Aceite

- Username inexistente vira `✗` no `doctor`, não warning no `run`.
- Canal do qual não se é membro é distinguido de canal inexistente.
- `doctor` sem sessão não quebra e diz que não validou.

---

## 4. `garimpo backfill --telegram` — IMPLEMENTADO (2026-08-20)

Absorveu os passos 1 e 2 da seção 1. Um comando substitui os dois scripts
avulsos:

```
garimpo backfill --telegram --days 30
```

Para cada fonte habilitada com `last_msg_id = 0`, resolve, acha o `msg_id`
correspondente a `--days` atrás via `msg_id_at` (novo método do
`MTProtoClient` Protocol; no Telethon usa `get_messages(offset_date=...)`,
que é por data e não depende de chutar o volume diário do canal), semeia o
ponteiro e laça `recover_source(alert=False)` até esgotar.

Fonte que já tem ponteiro é preservada. Backend sem `msg_id_at` (pyro) avisa e
cai para o início do canal em vez de quebrar.

Verificado num reset real: 28.759 mensagens de 7 fontes, janela de 30 dias
exata, 7 modelos cruzando `min_samples`, e **233 alertas todos `suppressed`** —
nenhuma notificação enviada durante o backfill.

O `Pipeline` é construído com `dry_run=True` de propósito: isso força canal
console e dispensa cliente Telegram conectado, então o backfill funciona mesmo
com `alerts.channel: saved_messages`. `dry_run` não afeta escrita no banco.

## 5. `stats` deve responder "está funcionando?"

**Custo:** baixo.

Hoje devolve contadores crus: `raw_by_status`, `price_history`,
`alerts_by_level`. Não responde a única pergunta que importa na primeira
semana — *o score já ligou?*

Lembrando que abaixo de `min_samples=12` o `rules.py:113` cai num atalho que é
só filtro de preço máximo. O usuário recebe alertas e acredita que são
estatísticos, quando não são. Essa confusão é invisível hoje.

### Desenho

Acrescentar ao `stats`:

- **Funil com taxa de parse:** `triaged_out` / `parse_failed` / `parsed`, e a
  razão `parsed / (parsed + parse_failed)`. É o sinal de que o grupo mudou de
  formato ou de que o catálogo não cobre o que a fonte posta.
- **Prontidão por modelo vigiado:** `n` na janela de 90 dias contra
  `min_samples`, marcando quais têm baseline de verdade.
- **Aviso explícito** quando um modelo do `watch` está abaixo do limiar, com o
  texto dizendo que os alertas dele não são estatísticos.

### Aceite

- Com banco vazio, `stats` diz que nenhum modelo tem baseline.
- Modelo que cruza `min_samples` aparece marcado.
- Modelo no `watch` sem amostra suficiente gera aviso visível.

---

## 6. Gap recovery só acontece no boot

**Custo:** médio. Só dói em host que dorme — mas é perda silenciosa de dado.

`run_daemon` chama `recover_source` uma única vez, antes de registrar o
handler ao vivo:

```python
for src in resolved:
    await recover_source(client, pipeline, src, alert=True)
client.on_new_message(resolved, _handle)
```

O Telethon reconecta sozinho (`auto_reconnect=True`), então o daemon
*sobrevive* a uma queda de rede ou a um sleep — e volta a receber eventos a
partir do instante da reconexão. As mensagens do intervalo **nunca são
buscadas**. Processo suspenso e retomado não é processo reiniciado.

Numa VPS 24/7 isso quase não aparece. Em notebook, aparece toda noite: fechar
a tampa com o daemon carregado perde a madrugada inteira, enquanto parar e
subir de manhã não perde nada, porque o boot faz o recovery. É contraintuitivo
o bastante para o usuário nunca descobrir sozinho.

### Desenho

Detectar reconexão e re-rodar `recover_source` antes de voltar ao modo ao
vivo. O Telethon expõe isso via handlers de `Connected`/`Disconnected`; a
alternativa mais simples é um laço que compara `last_msg_id` guardado com o id
da última mensagem do canal em intervalo fixo, e chama `recover_source` quando
divergirem além de uma folga.

Cuidado obrigatório: passar `alert=True` mas confiar no `ALERT_MAX_AGE` de 15
minutos, senão um recovery após 8 horas dispara centenas de notificações.

### Aceite

- Daemon rodando, rede cortada por 30 minutos, restaurada: as mensagens do
  intervalo aparecem em `raw_messages` sem reiniciar o processo.
- Nenhum alerta é enviado para mensagem mais velha que `ALERT_MAX_AGE`.
- Sem reconexão, nenhuma chamada extra ao Telegram (não pode virar polling).

---

## 7. Já resolvido nesta sessão

**macOS.** O repo só tinha `garimpo.service` (systemd) e `deploy/` de nuvem.
Notebook Apple não tinha caminho. Agora há
`deploy/com.garimpo.daemon.plist` — LaunchAgent com `KeepAlive`,
`ThrottleInterval` e log em arquivo, envelopado em
`caffeinate -ims` para o sono por ociosidade não abrir buraco no histórico.
Tampa fechada continua dormindo; isso não tem solução boa em notebook.

---

## 8. Não confundir com estes

**`retention_raw_days`.** Durante diagnóstico convém subir para não perder o
funil; em produção 30 é o certo. Vale um aviso no `doctor` quando o valor
estiver absurdo, mas não é bug.

**`within_minutes=10` no dedupe de oferta** (`store/repo/offers.py:68`).
Calibrado para uma fonte. Com sete canais cross-postando a mesma promoção ao
longo de horas, o mesmo evento de preço entra várias vezes no baseline. É
decisão de calibração e precisa de dado real para escolher o número — não
mexer no escuro.
