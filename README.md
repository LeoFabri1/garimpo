# Garimpo

Deal prospecting engine for Telegram — reads the deal groups you already
follow, learns historical prices, and alerts you only when an offer is
statistically exceptional.

*Garimpo* is Portuguese for prospecting: sifting through tons of gravel
to find the nugget.

**Status:** Sprint 0 concluída; Sprint 1 (núcleo determinístico) em andamento —
parse, catálogo GPU e scoring testáveis sem rede. Ver [docs/SPRINTS.md](docs/SPRINTS.md).

## Aviso (leia antes)

- Precisa de **host 24/7** (VPS ~€4/mês ou Raspberry Pi). Notebook que dorme
  corrompe o histórico de preços.
- Usa **userbot** (MTProto). Há risco de ban — use **número secundário**.
- Não é SaaS zero-config. Público-alvo: quem já roda Docker/systemd em casa.

## Quickstart (desenvolvimento)

```bash
git clone https://github.com/LeoFabri1/garimpo.git
cd garimpo
uv sync
uv run garimpo --help
```

Com backend Telegram (a partir da Sprint 3):

```bash
uv sync --extra telethon
cp .env.example .env          # colar TG_API_ID / TG_API_HASH
cp config/quickstart.yaml config/config.yaml
```

## Instalação via PyPI

O pacote será publicado como **`garimpo`**. Até o primeiro release, use o clone
acima.

```bash
pip install "garimpo[telethon]"   # quando 0.1.0+ estiver no índice
garimpo --help
```

Extras: `telethon`, `pyro`, `mcp`, `dev`. Configuração de build, versionamento
e publish para maintainers: **[docs/publishing.md](docs/publishing.md)**.

## Documentação

| Documento | Conteúdo |
|-----------|----------|
| [DESIGN-2.md](DESIGN-2.md) | Design técnico completo (fonte canônica) |
| [docs/DESIGN.md](docs/DESIGN.md) | Ponte estável em `docs/` → design canônico |
| [docs/SPRINTS.md](docs/SPRINTS.md) | Sprints 0–9, PRs diários, critérios de pronto |
| [docs/publishing.md](docs/publishing.md) | PyPI: metadados, extras, build, Trusted Publishing |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Setup e good first issues |
| [SECURITY.md](SECURITY.md) | Sessão, tokens, revogação |

## Roadmap (resumo)

| Versão | Critério de conclusão |
|--------|------------------------|
| **v0.1** | Alerta útil sem nenhuma API key (Sprints 0–4) |
| **v0.1.1** | Critical acorda, normal não; Docker + heartbeat |
| **v0.2** | LLM só como fallback de parse; `simulate` |
| **v0.3** | Servidor MCP + webhooks + export |
| **v0.4** | Novas categorias; telemetria opt-in; backend pyro |
| **v0.5** | Painel web local somente leitura |

## License

MIT — see [LICENSE](LICENSE).
