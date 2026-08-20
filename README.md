# Garimpo

Deal prospecting engine for Telegram — reads the deal groups you already
follow, learns historical prices, and alerts you only when an offer is
statistically exceptional.

**Sem IA.** O parse é regex e casamento de alias contra um catálogo curado à
mão; a decisão de alertar é estatística — mediana ponderada, MAD e percentil
sobre a janela de 90 dias. Nenhuma inferência, nenhum modelo, nenhuma chave de
API. Um alerta sempre pode ser explicado pelo número que o gerou.

*Garimpo* is Portuguese for prospecting: sifting through tons of gravel
to find the nugget.

**Status:** pre-alpha, uso pessoal. Pipeline offline (parse → score → alert),
ingest do Telegram, backfill, MCP, webhook, export CSV e painel local estão de
pé; telemetria é opt-in e vem desligada. Sem dependência de IA. Não é serviço, não tem suporte, e o
risco de banimento do número é seu — leia o [DISCLAIMER.md](DISCLAIMER.md).

## Aviso — leia antes de fazer login

O Garimpo autentica como **conta de usuário** (userbot / MTProto), **não**
como bot do BotFather.

Os [Content Licensing Terms](https://telegram.org/tos/content-licensing) do
Telegram concedem licença de acesso a dados para três categorias: **Client**,
**Bot** e **Mini App**. O Garimpo é um daemon de leitura e não se apresenta
como nenhuma das três. O
[API ToS §3.3](https://core.telegram.org/api/terms) pede que apps que acessam
conteúdo de canais suportem sponsored messages, e o Garimpo não implementa
esse suporte — um processo sem interface não tem onde exibi-las.

Leia os termos e **avalie se o seu uso está coberto** antes de rodar.

**Experimento pessoal, pre-alpha, sem suporte. Não recomendado para uso
geral.** Existe risco real de restrição ou banimento do número usado na sessão,
e ele é seu. Leia o [DISCLAIMER.md](DISCLAIMER.md) antes de rodar — ele lista o
que o projeto faz, o que explicitamente **não** faz, e o que você assume.

- Use um **número secundário** (chip/eSIM só para isso).
- **Não** use o Telegram principal (trabalho, família, banco, 2FA).
- O cliente **só lê** os grupos monitorados (não envia, não reage, não marca
  como lido, não lista membros). Escrita, se houver, é só para você
  (Saved Messages / bot).
- `garimpo login` exige digitar `secundario` para confirmar que você leu isto.

Também precisa de **host 24/7** (VPS ~€4/mês ou Raspberry Pi). Notebook que
dorme corrompe o histórico de preços. Não é SaaS zero-config.

Detalhes: [DISCLAIMER.md](DISCLAIMER.md) · [docs/login.md](docs/login.md) · [SECURITY.md](SECURITY.md).

## Quickstart (desenvolvimento)

```bash
git clone https://github.com/LeoFabri1/garimpo.git
cd garimpo
uv sync
uv run garimpo --help
uv run garimpo doctor -c config/quickstart.yaml
uv run garimpo run --dry-run -c config/quickstart.yaml \
  -m 'RTX 5070 Ti ASUS — R$ 5.799 no PIX Kabum'
uv run garimpo stats -c config/quickstart.yaml
```

Com backend Telegram (número **secundário**):

```bash
uv sync --extra telethon
cp .env.example .env          # TG_API_ID / TG_API_HASH (my.telegram.org)
cp config/quickstart.yaml config/config.yaml
uv run garimpo login --qr     # aviso de ban + digite: secundario
# edite config.yaml: adicione seus canais em sources:
uv run garimpo doctor
uv run garimpo backfill --telegram --days 30   # popula o histórico, sem alertar
uv run garimpo simulate --days 30              # veja o volume antes de ligar o alerta
uv run garimpo run                             # daemon
```

O `backfill` é o passo que falta na maioria das tentativas. Sem ele, `run`
começa pela mensagem **mais antiga** do canal — num grupo ativo desde 2020,
isso é preço de placa de vídeo de cinco anos atrás, e nada parece errado.

### Rodar em background

```bash
garimpo daemon start      # instala o LaunchAgent e sobe
garimpo daemon status     # no ar? desde quando entrou mensagem?
garimpo daemon logs -f    # acompanha
garimpo daemon restart    # aplica mudança de config
garimpo daemon stop
```

`start` gera o LaunchAgent com os caminhos desta máquina — não é preciso editar
plist. `restart` é o que você quer depois de mexer no `config.yaml`, porque o
daemon lê a configuração só no boot.

macOS por enquanto (launchd). No Linux, use `garimpo.service` com systemd; o
comando diz isso se você tentar.

## Instalação

**Não publicado no PyPI**, e sem previsão. O projeto autentica como conta de
usuário do Telegram (ver [DISCLAIMER.md](DISCLAIMER.md)); distribuir isso como
pacote instalável facilitaria o uso por quem não leu o aviso de risco. Use o
clone acima.

Extras disponíveis no clone: `telethon`, `pyro`, `mcp`.

## Documentação

| Documento | Conteúdo |
|-----------|----------|
| [docs/quickstart.md](docs/quickstart.md) | Do clone ao primeiro alerta |
| [docs/login.md](docs/login.md) | api_id/api_hash + QR login + risco de ban |
| [docs/tos-compliance.md](docs/tos-compliance.md) | Posição frente ao ToS e implementações pendentes |
| [docs/hosting.md](docs/hosting.md) | VPS, Docker, heartbeat, custo |
| [docs/onboarding.md](docs/onboarding.md) | Primeira execução: lacunas do CLI e scripts avulsos |
| [docs/baseline.md](docs/baseline.md) | Viés de seleção do baseline e âncora de varejo |
| [DISCLAIMER.md](DISCLAIMER.md) | Risco de ban, responsabilidade, uso não econômico |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Setup e good first issues |
| [SECURITY.md](SECURITY.md) | Sessão, tokens, revogação |

## Roadmap (resumo)

| Versão | Critério de conclusão |
|--------|------------------------|
| **v0.1** | ✅ Alerta útil sem nenhuma API key |
| **v0.1.1** | ✅ Critical acorda, normal não; Docker + heartbeat |
| **v0.2** | ✅ `simulate`; backfill; daemon; watchdog; sem IA |
| **v0.3** | Servidor MCP + webhooks + export |
| **v0.4** | Novas categorias; telemetria opt-in; backend pyro |
| **v0.5** | Painel web local somente leitura |

## License

MIT — see [LICENSE](LICENSE).
