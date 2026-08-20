# ToS: posição atual e implementações pendentes

Onde o Garimpo está frente aos termos do Telegram, e o que dá (ou não dá) para
mudar no código. Documento de trabalho — as seções 2–4 são propostas ainda não
implementadas; a seção 1 e os avisos no README/login refletem o estado atual.

Fontes, verificadas direto em telegram.org:

- [Content Licensing / AI Scraping Terms](https://telegram.org/tos/content-licensing)
- [API Terms of Service](https://core.telegram.org/api/terms)
- [Terms of Service](https://telegram.org/tos)

Nenhuma dessas páginas exibe data de atualização. Reconfira o texto antes de
tomar decisão com base neste doc.

---

## 1. Onde estamos

Os Content Licensing Terms concedem licença de acesso a dados numa lista
fechada de três categorias:

> Telegram permits access to data required to launch and operate a legitimate
> third-party Telegram **Client**, Telegram **Bot**, or Telegram **Mini App**,
> provided that it operates in full compliance with the Telegram Terms of
> Service [...] on a retractable, limited, non-exclusive, non-transferable and
> non-sublicensable basis solely to the extent strictly required to operate the
> relevant service.

O Garimpo é um daemon de leitura e não se apresenta como nenhuma das três. A
diferença em relação a "zona cinza" é que não se trata de omissão dos termos:
existe uma concessão explícita e enumerada, e não há base para presumir que
esta ferramenta esteja abrangida por ela.

Este doc descreve os termos e o que o código faz. A avaliação jurídica do seu
uso concreto é sua, e nada aqui substitui orientação profissional.

Dois pontos concretos decorrem disso:

**API ToS §3.3** — o Garimpo não implementa suporte a sponsored messages:

> If your app allows accessing content from Telegram channels, you must include
> support for official sponsored messages in Telegram channels and may not
> interfere with this functionality.

**Cláusula de AI** — motivou a remoção do enricher (seção 2):

> Telegram firmly prohibits the scraping, indexing, harvesting, aggregation or
> use of data obtained from its platform to train, fine-tune, validate or
> otherwise engage in the development, enhancement, benchmarking or deployment
> of artificial intelligence, machine learning models and similar technologies.

Inferência para extração não é treino, mas "deployment of [...] models" sobre
dado da plataforma é redação larga o bastante para cobrir o enricher.

### O que já está certo

Não mexer nisto sem motivo — é o que segura o risco de banimento hoje:

- Nenhuma chamada a `GetParticipants` / `iter_participants`. É o padrão que o
  Telegram pune mais agressivamente, e não o usamos.
- Nenhum `join_chat` / `JoinChannel`. Depende de você já ser membro.
- Nenhum `mark_read` / `ReadHistory` — não adultera status de leitura, o que
  atenderia o §1.4 ("tampering with the 'read' statuses").
- Única escrita: `send_message("me")`, Saved Messages
  (`telethon_client.py:143`, `pyro_client.py:177`).
- Nenhum caminho de IA: o enricher por LLM foi removido do projeto.
- Telemetria opt-in, off por default, e manda só dado derivado
  (`model_key`, `price`, `store`, `timestamp`) — nunca conteúdo de mensagem.
- Divulgação do uso da API do Telegram no README, atendendo o §2.2.

---

## 2. Cláusula de AI — RESOLVIDA POR REMOÇÃO (2026-08-20)

Os Content Licensing Terms proíbem usar dado da plataforma para "development,
enhancement, benchmarking or deployment of artificial intelligence, machine
learning models and similar technologies".

O projeto tinha um enricher opcional que mandava o texto bruto da mensagem
para um LLM externo quando o parser falhava. Vinha desligado, e a defesa —
inferência não é treino — era discutível, porque "deployment" é redação larga.

**O código foi removido**, não apenas desligado. Some o `enrich/` inteiro, o
`LlmSettings`, o status `llm_pending` e o `extracted_by="llm"`. O projeto
agora não tem caminho para violar essa cláusula: não existe modelo para
implantar.

Os números que motivaram a decisão: de 6.750 mensagens em `parse_failed`, só
119 (1,8%) eram sequer plausivelmente oferta de GPU, e essas estavam sendo
rejeitadas corretamente — PC montado, placa fora do catálogo, anúncio sem
preço. O enricher processaria cafeteira e ar-condicionado, pagando por token.

A tabela `enrich_queue` da migration 002 fica no schema. Migration aplicada
não se reescreve, a tabela está vazia, e uma migration destrutiva por estética
é risco sem ganho.

## 3. Sponsored messages (§3.3) — questão aberta

**Status:** não decidido. **Custo estimado:** ~meio dia, se for adiante.

A cláusula pede duas coisas: **incluir suporte** e **não interferir**. O
Garimpo hoje não implementa nenhuma das duas.

### Passo 0, obrigatório antes de qualquer desenho

Confirmar a superfície da API na versão fixada (`telethon==1.44.0`): quais
requests de sponsored messages existem, suas assinaturas, e a qual peer se
aplicam. O schema MTProto mudou de layer para layer nesse ponto — inclusive de
namespace — então **não assuma nomes de símbolo**. Verifique antes:

```bash
uv run python -c "
import telethon
from telethon.tl.functions import messages, channels
print(telethon.__version__)
print([n for n in dir(messages) if 'Sponsored' in n])
print([n for n in dir(channels) if 'Sponsored' in n])
"
```

Se a versão fixada não expuser esses requests, este item vira "subir o pin do
Telethon" antes de qualquer outra coisa, e o custo muda.

Em `telethon==1.44.0` (pin atual), a introspecção expõe:
`GetSponsoredMessagesRequest`, `ViewSponsoredMessageRequest`,
`ClickSponsoredMessageRequest`, `ReportSponsoredMessageRequest` (namespace
`messages`) e `RestrictSponsoredMessagesRequest` (namespace `channels`). A opção
B acima usaria `ViewSponsoredMessageRequest` — exatamente o ponto em disputa.

### Opções em disputa — não escolher sem revisar

**A. Encaminhar sem marcar como vista**

Buscar sponsored messages dos canais que lê e encaminhar para Saved Messages,
**sem** chamar o request de "viewed". O usuário vê o anúncio; nenhuma impressão
é fabricada. Risco: pode não satisfazer "include support" se o Telegram
interpretar "support" como exibir *e* registrar a visualização.

**B. Encaminhar e chamar "viewed"**

Mesmo fluxo, mas chama o request de viewed no momento do encaminhamento. Risco
oposto: esse request **é a impressão que o anunciante paga**. Dispará-lo de um
daemon, sem humano olhando, pode ser pior que não fazer nada — fabrica métrica
de anunciante sob a mesma cláusula que proíbe interferir.

**C. Não implementar**

Manter o status quo. O §3.3 continua sem resposta no código; o aviso no README
diz isso explicitamente.

Qualquer implementação (A ou B) precisaria ainda de:

- Estender o `MTProtoClient` Protocol (`src/garimpo/ingest/base.py`) com
  `fetch_sponsored(source) -> list[SponsoredMessage]` e, **só se a opção B for
  escolhida**, `mark_sponsored_viewed(...)`.
- Implementar no `TelethonClient`. No `PyroClient`, levantar
  `NotImplementedError` — documentar que o backend pyro não atende o §3.3.
- Loop novo em `listener.py`, junto de `_quiet_flush_loop` e `_retention_loop`:
  intervalo folgado, falha não derruba o daemon (mesmo padrão do
  `enricher_loop`).
- Config `telegram.sponsored: forward | off`, default `off` até a opção ser
  decidida. Quem ligar deve saber qual opção (A ou B) está ativa.
- **Não** submeter sponsored messages ao pipeline de parse/score. Elas não são
  oferta e contaminariam o baseline de preço.

### Riscos comuns às opções A e B

- Intervalo agressivo é FloodWait. Comece folgado (horas, não minutos).
- Sponsored messages só existem em canais grandes; a lista vazia é o caso
  comum e não é erro.

### Aceite (quando houver decisão)

- Sponsored message nunca vira `raw_message` nem entra no histórico de preço.
- `sponsored: off` não faz nenhuma chamada.
- Falha na busca não derruba o daemon.

---

## 4. Backend Bot API

**Custo:** ~1 dia de código. **Custo real:** o histórico de preço.

É o caminho que se **apresenta como Bot** dentro das três categorias que os
termos enumeram. Está documentado aqui como decisão de produto, não como
refactor pendente — porque o que se perde é o núcleo do valor.

### O que se perde

1. **Bot só recebe updates de chats onde foi adicionado.** Você não lê um canal
   de ofertas sem o dono adicionar seu bot. Isso elimina a proposta central —
   "lê os grupos de ofertas que você já segue" — para a maioria das fontes.
2. **Privacy mode.** Em grupos vem ligado: só comandos e replies, a menos que o
   bot seja admin.
3. **Bots não leem histórico.** Não existe equivalente de `iter_messages` na
   Bot API. `fetch_since` retornaria vazio. O `recovery.py` **não quebra** com
   fetch vazio — retorna 0 e segue — mas a recuperação de gap vira **no-op
   silencioso**: o daemon que cai perde as mensagens da queda sem aviso. Esse é
   o problema real, não um crash.
4. **Backfill morre.** Sem histórico, `tools/backfill.py` não tem de onde
   partir. O baseline estatístico começa do zero e leva semanas até o score
   valer alguma coisa — e o score é o produto.

### Se ainda assim for pra frente

- `src/garimpo/ingest/clients/bot_client.py` implementando o Protocol.
  `httpx` já é dependência; não precisa de lib nova.
- `on_new_message` via long polling `getUpdates`; `send_self` via `sendMessage`
  para o chat_id do dono; `resolve_source` via `getChat`.
- `fetch_since` retorna `[]`. O `doctor` deve avisar, em backend bot, que não
  há gap recovery — hoje o `recovery.py` degrada sem avisar, e isso precisa
  ficar visível.

---

## 5. Fora de alcance

**Telegram Client** — o §1.3 exige que "all the basic features of the main
Telegram apps function correctly", com a frase escopada a "as a client
developer". Isso é escrever um app de mensagens completo. Não é o projeto.

**Mini App** — roda dentro do Telegram e não tem acesso a histórico de canais
arbitrários. Não serve para o caso de uso.

**Consentimento por usuário** — os termos abrem exceção com consentimento
"explicit, informed, affirmative and continued" de *todos* os usuários
envolvidos, limitado àquele chat, e não transferível entre contextos. Num canal
público de ofertas com milhares de membros, é inviável na prática.

---

## 6. Pesquisa de alternativas (2026-08-20)

Quatro frentes paralelas investigaram se existe caminho para operar dentro dos
termos preservando o produto. Resumo do que voltou, com o que é verificado e o
que ficou em aberto.

### 6.1 Dentro do Telegram: não há caminho

**Business Bots não serve** — era a hipótese mais promissora e caiu. O schema
`inputBusinessBotRecipients` (`core.telegram.org/api/bots/connected-business-bots`)
tem como escopos apenas `existing_chats`, `new_chats`, `contacts`,
`non_contacts`, `users`, `exclude_users`. Todos são conceitos de conversa
privada 1:1; **não existe flag para canal ou grupo**. É automação de inbox — um
bot que responde quem manda DM para a conta —, não uma ponte para o que a conta
acompanha. (Achado lateral verdadeiro mas irrelevante: conectar bot business
não exige Premium, ao contrário do que o blog oficial sugere.)

**Bot API tem três travas duras:**

- Não existe equivalente de `getHistory`. Backfill é impossível. O texto do
  "guest mode" é explícito: *"does not grant access to a chat's message
  history"*.
- Um bot **não entra sozinho** em canal via link de convite. Precisa de um
  humano com permissão adicionando, canal por canal.
- `my.telegram.org` não é processo de aprovação — emite `api_id` em
  autosserviço. Não há trilha formal para pedir licença especial.

Em grupo, com privacy mode desligado (ou bot como admin), o bot vê tudo. Em
canal, a documentação diz "member" mas na prática exige admin. De qualquer
forma, depende do dono aceitar.

### 6.2 Discord é a única alternativa estruturalmente equivalente

A exigência formal é idêntica — bot convidado por admin — mas a diferença
cultural é decisiva: servidores de Discord rodam dezenas de bots de terceiros
como comportamento normal; canais de Telegram, não.

- API de bot oficial e licenciada exatamente para ler canal em tempo real,
  latência de WebSocket comparável ao MTProto.
- Self-bot é proibido pelo ToS do Discord, igual ao Telegram — a diferença é
  que existe a segunda via.
- Desde 10/jun/2026 o **Message Content Intent** (privileged) é autoativado no
  Developer Portal abaixo de **10.000 usuários únicos alcançados**. Um bot
  pessoal em poucos servidores não chega perto do gatilho.

Comunidades BR encontradas: **Cuponizze** e **Bizu Garimpo**.
**Não verificado** — tamanho, atividade e se aceitam bot de terceiro; os sites
devolveram 403. Confirmar antes de qualquer decisão de arquitetura.

### 6.3 Feeds RSS: existem, mas são editoriais

Verificados no corpo da resposta (XML real, não só header):
`tecnoblog.net/feed/`, `adrenaline.com.br/feed/`, `canaltech.com.br/rss/`
(este com **WebSub**, ou seja push em vez de polling), `showmetech.com.br/feed/`,
`olhardigital.com.br/feed/`, `hardware.com.br/feed/`.

Limitação estrutural: granularidade de **artigo**, não de oferta individual.
Não carregam cupom, método de pagamento nem seller. Servem de contexto, não de
gatilho.

Reddit fechou: `reddit.com/robots.txt` devolve página de bloqueio e o antigo
truque de acrescentar `.json` sem autenticação não funciona mais.

### 6.4 Varejo: scraping educado, não API

Nenhuma API oficial brasileira serve para consultar preço de terceiros — todas
são seller-facing (exigem CNPJ) ou são afiliado-de-clique. Não existe "Keepa
brasileiro": Zoom e Buscapé mostram histórico só na interface, e a API que
documentam é para lojista **enviar** catálogo.

| Loja | robots.txt | Situação |
|------|-----------|----------|
| **Kabum** | `Allow: /` para produto e busca | Preço em JSON no `__NEXT_DATA__` do HTML server-renderizado. Verificado. |
| **Shopee** | `Crawl-delay: 1` explícito para UA genérico | Tolerância declarada. |
| **Pichau** | Permite, mas `Disallow: /*?*` | Magento; instável no teste (Cloudflare + manutenção). |
| **Terabyte** | 403 — nem o robots.txt é servido | Cloudflare challenge ativo. |
| **Magazine Luiza** | 403 — Akamai Bot Manager | Idem. |

**Terabyte e Magalu ficam fora.** Contornar bot management ativo desloca a
conduta de "raspagem educada" para "evasão de proteção anti-bot" — uma linha
jurídica pior que a do Telegram, e desnecessária.

### 6.5 A exposição jurídica real é menor do que parece

*Não é aconselhamento jurídico.*

- **Violar ToS é inadimplemento contratual**, cuja sanção prevista é uma só:
  perder a conta. Não foi encontrado nenhum caso brasileiro de plataforma
  processando usuário por violar termos de uso.
- O precedente mais citado em raspagem — **Catho × Curriculum** — é empresa
  contra concorrente direto, com programa feito para burlar controle e
  finalidade econômica. Foi condenada por **concorrência desleal**, não por
  descumprir ToS. Estruturalmente distante deste caso.
- **Penal não alcança**: o art. 154-A do CP exige dispositivo *alheio* e
  *violação de mecanismo de segurança*. Conta própria, credencial própria, API
  acessada como projetada — falta elemento típico. O Brasil sempre exigiu esse
  elemento, ou seja, nunca teve o "exceeds authorized access" amplo do CFAA que
  os EUA só restringiram em *Van Buren* (2021).
- **Direito autoral não protege** anúncio factual de preço, e o Brasil não
  adotou o direito *sui generis* de banco de dados da diretiva 96/9/CE.
- **A jurisprudência corre a favor do usuário**: TJCE e TJMT condenaram
  plataformas por banimento sem motivação, com ônus da prova da infração sobre
  a plataforma.
- **Padrão empírico de banimento**: `GetParticipants`, envio em volume, adição
  de contatos em massa, e sobretudo sinais de conta — número virtual, conta
  nova sem histórico orgânico, IP de datacenter. Leitura de histórico em ritmo
  moderado é descrita como sustentável indefinidamente. **O Garimpo não faz
  nenhuma das condutas de risco.**

Ressalvas honestas: a doutrina majoritária lê o art. 4º, I da LGPD de forma
estreita e episódica, e coleta automatizada contínua é mais discutível que uma
agenda de contatos — a leitura literal favorece, a doutrinária menos. E não
encontrar caso de ban por leitura passiva é ausência de evidência, limitada
pela cobertura da busca, não prova de segurança.

### 6.6 Conclusão

Não existe caminho para "legalizar" a ingestão do Telegram preservando o
produto. Mas a pesquisa reposiciona a pergunta: o que se estaria legalizando
tem como pena máxima a perda de um número secundário, e a exposição jurídica
*stricto sensu* é próxima de nula para uso pessoal e não econômico.

Decisões que decorrem disso:

1. **Manter o Telegram como entrada de evento.** É onde a curadoria humana
   existe, e a oferta relâmpago é uma receita (cupom + PIX + seller + estoque)
   que nenhum feed de catálogo carrega.
2. **Discord vale investigar** como fonte redundante e totalmente licenciada.
   Custo de entrar em dois servidores e observar é quase zero.
3. **Nunca monetizar.** As quatro frentes convergiram nisso de forma
   independente — é a única decisão que criaria exposição jurídica de verdade.
   Ver [DISCLAIMER.md](../DISCLAIMER.md).
