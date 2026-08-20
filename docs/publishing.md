# Publicação no PyPI

> **SUSPENSO (2026-08-20).** O projeto não será publicado no PyPI e o workflow
> de release está desativado (`.github/workflows/publish.yml.disabled`).
> Distribuir como pacote instalável facilitaria o uso por quem não leu o
> [DISCLAIMER.md](../DISCLAIMER.md), e o Garimpo autentica como conta de
> usuário do Telegram. Este documento fica como referência caso a decisão mude.


Como o pacote `garimpo` é construído, versionado e publicado. Destinado a
**maintainers**. Usuários finais: veja a seção de instalação no [README](../README.md).

Fonte de configuração: [`pyproject.toml`](../pyproject.toml) (PEP 621 + Hatchling).

---

## Visão geral

| Campo | Valor |
|-------|--------|
| Nome no PyPI | `garimpo` |
| Build backend | `hatchling` |
| Layout | `src/garimpo` |
| Python | `>=3.12` |
| Entrypoint | `garimpo = "garimpo.cli:app"` |
| Licença | MIT |

O **core** no PyPI **não** puxa Telethon. Backends MTProto e MCP são extras —
instalação típica de quem vai rodar o daemon:

```bash
pip install "garimpo[telethon]"
# ou
uv pip install "garimpo[telethon]"
```

---

## O que o `pyproject.toml` declara

### Metadados (`[project]`)

- `name`, `version`, `description`, `readme`, `license`, `requires-python`
- `authors`, `keywords`, `classifiers` (aparecem na página do PyPI)
- `dependencies` — runtime mínimo (Pydantic, Typer, httpx, …)
- `optional-dependencies`:
  - `telethon` → `telethon==1.44.0` (**pin exato**)
  - `pyro` → `pyrotgfork>=2.2` (backend alternativo)
  - `mcp` → `mcp>=1.0`
- `urls` — Homepage / Repository / Issues / Documentation
- `scripts.garimpo` — console script instalado no PATH

### Build (`[tool.hatch.build…]`)

- Wheel: pacote em `src/garimpo`
- Sdist: inclui `src/`, `catalog/`, `config/`, `docs/`, `tests/`, LICENSE, README

**Não** entram no artefato (via `.gitignore` / ausência no sdist): `.env`,
`data/`, `*.session`, `.venv/`.

### Ferramentas locais

- `[dependency-groups] dev` — usado por `uv sync` no clone do repo
- `[tool.pytest]`, `[tool.ruff]`, `[tool.mypy]` — qualidade, não afetam o wheel

---

## Extras e como o usuário instala

| Extra | Quando | Comando |
|-------|--------|---------|
| *(nenhum)* | só CLI / libs core (parse, score, …) | `pip install garimpo` |
| `telethon` | daemon / login (v0.1+) | `pip install "garimpo[telethon]"` |
| `pyro` | backend alternativo (v0.4+) | `pip install "garimpo[pyro]"` |
| `mcp` | `garimpo mcp` (v0.3+) | `pip install "garimpo[mcp]"` |
| vários | — | `pip install "garimpo[telethon,mcp]"` |

Ferramentas de desenvolvimento **não** são um extra publicado: vivem em
`[dependency-groups] dev` (PEP 735) e o `uv sync` já as instala no clone.

Com uv a partir do repo:

```bash
uv sync --extra telethon
uv sync --all-extras          # telethon + pyro + mcp (+ grupo dev)
```

---

## Versionamento

1. Bump `version` em `pyproject.toml` **e** `src/garimpo/__init__.py` (`__version__`).
2. Convention: SemVer. Pré-v0.1 pode ficar em `0.0.x`; primeiro release útil = `0.1.0`.
3. Tag git alinhada: `v0.1.0`.
4. Classifiers: atualizar `Development Status` quando sair de Pre-Alpha.

Não republicar a **mesma** versão no PyPI — o índice é imutável. Se o upload
falhou no meio, use a próxima versão patch.

---

## Build local (smoke)

Requer [uv](https://docs.astral.sh/uv/):

```bash
uv sync
uv build
ls dist/
# garimpo-0.1.0-py3-none-any.whl
# garimpo-0.1.0.tar.gz
```

Instalar o wheel localmente para validar o entrypoint:

```bash
uv pip install "dist/garimpo-*.whl[telethon]"
garimpo --version
garimpo --help
```

Checklist antes de publicar:

- [ ] `uv run pytest` verde
- [ ] `uv run ruff check src tests` verde
- [ ] `garimpo --version` bate com `pyproject.toml`
- [ ] README e classifiers coerentes com o estado do release
- [ ] Nenhum segredo no sdist → o comando abaixo deve sair vazio. Ancore os
      padrões: um `grep session` solto casa com `auth/session.py` e grita lobo.

```bash
tar tzf dist/*.tar.gz | grep -E '\.session$|(^|/)\.env$|\.db$|(^|/)data/'
```

---

## Conta e autenticação PyPI

### Opção A — Trusted Publishing (recomendado)

1. Crie o projeto em https://pypi.org/manage/projects/ (ou no primeiro upload).
2. Em **Publishing** do projeto, adicione um publisher GitHub Actions:
   - Owner / repo / workflow filename / environment (opcional)
3. No CI, use `pypa/gh-action-pypi-publish` com `permissions: id-token: write`.
4. **Não** precisa de API token no GitHub Secrets.

### Opção B — Token de API

1. PyPI → Account settings → API tokens → scope no projeto `garimpo`.
2. Guarde como `PYPI_TOKEN` (ou `UV_PUBLISH_TOKEN`).
3. Nunca commitar o token.

TestPyPI: https://test.pypi.org — mesma ideia, índice separado para ensaio.

---

## Publicar com uv

### TestPyPI (ensaio)

```bash
uv build
uv publish --publish-url https://test.pypi.org/legacy/ --token "$TEST_PYPI_TOKEN"
```

Instalar o ensaio:

```bash
pip install -i https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ "garimpo==0.1.0"
```

(`extra-index-url` porque as deps runtime vêm do PyPI real.)

### PyPI produção

```bash
uv build
uv publish --token "$PYPI_TOKEN"
```

Com Trusted Publishing, o upload acontece no workflow após a tag; localmente
só use token se souber o que está fazendo.

---

## Workflow GitHub

Já configurado em [`.github/workflows/publish.yml`](../.github/workflows/publish.yml).

Dois gatilhos:

- **GitHub Release publicado** → build, validações, upload para PyPI
- **`workflow_dispatch`** → escolha `testpypi` ou `pypi` manualmente (use TestPyPI
  para o ensaio antes do primeiro release)

Antes de qualquer upload o job `build` recusa a publicação se:

- a tag `vX.Y.Z` não bater com `version` do `pyproject.toml` (versão errada no
  PyPI é irreversível — não há como reenviar o mesmo número)
- `twine check` reprovar os metadados
- o wheel instalado num venv limpo não rodar `garimpo catalog check` fora do
  checkout

Os jobs de upload usam GitHub Environments (`pypi` e `testpypi`), então você
pode exigir aprovação manual em Settings → Environments.

Disparo típico: criar GitHub Release a partir da tag `vX.Y.Z`.

---

## Nome do pacote e conflitos

- Nome reservado no PyPI: `garimpo`. Confirme disponibilidade antes do primeiro
  upload: https://pypi.org/project/garimpo/
- Se estiver tomado, **não** renomeie o módulo Python sem discussão — alinhar
  `name` no PyPI com import `garimpo` evita surpresa (`pip install X` → `import Y`).
- Homepage/Repository no `[project.urls]` devem apontar para este GitHub.

---

## O que não publicar / não embutir

- Credenciais Telegram, session files, dumps de `data/garimpo.db`
- Catálogos pessoais do usuário (`extra_paths`)
- Pins frouxos de Telethon (`>=`) — manter `==1.44.0` no extra

Affiliate rewriting, se existir no futuro, permanece **default off**
também no pacote publicado.

---

## Checklist do primeiro release público

1. [ ] Nome `garimpo` confirmado no PyPI
2. [ ] Trusted Publishing ou token configurado
3. [ ] Versão `0.1.0` (ou a acordada) em `pyproject.toml` — é a fonte única,
   `__version__` é lido da metadata instalada
4. [ ] README com `pip install "garimpo[telethon]"` e aviso userbot/host 24/7
5. [ ] Upload TestPyPI → smoke install → PyPI
6. [ ] Tag `v0.1.0` + GitHub Release
7. [ ] Atualizar classifiers / status no README

Até lá, o caminho suportado para usuários é **clone + `uv sync`**, não PyPI.
