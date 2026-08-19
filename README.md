# Garimpo

Deal prospecting engine for Telegram — reads the deal groups you already
follow, learns historical prices, and alerts you only when an offer is
statistically exceptional.

*Garimpo* is Portuguese for prospecting: sifting through tons of gravel
to find the nugget.

**Status:** Sprints 0–3. Offline pipeline + ingest Telethon (`login --qr`,
`run --once`). Alerta Saved Messages na Sprint 4. Ver [docs/SPRINTS.md](docs/SPRINTS.md).

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
uv run garimpo doctor -c config/quickstart.yaml
uv run garimpo run --dry-run -c config/quickstart.yaml \
  -m 'RTX 5070 Ti ASUS — R$ 5.799 no PIX Kabum'
uv run garimpo stats -c config/quickstart.yaml
```

Com backend Telegram:

```bash
uv sync --extra telethon
cp .env.example .env          # colar TG_API_ID / TG_API_HASH
cp config/quickstart.yaml config/config.yaml
uv run garimpo login --qr     # ver docs/login.md
uv run garimpo doctor
uv run garimpo run --once     # uma passada; ou `garimpo run` para daemon
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
| [docs/login.md](docs/login.md) | api_id/api_hash + QR login |
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
