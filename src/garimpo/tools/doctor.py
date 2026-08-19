"""garimpo doctor — local configuration diagnostics (Sprint 2: no network)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from garimpo.catalog import ModelIndex, load_gpu_catalog
from garimpo.settings import find_config_path, load_settings
from garimpo.store.db import connect, user_version


@dataclass
class CheckResult:
    ok: bool
    label: str
    detail: str | None = None
    warn: bool = False


def run_doctor(*, config: Path | None = None, quick: bool = False) -> list[CheckResult]:
    _ = quick  # network checks arrive in Sprint 3
    results: list[CheckResult] = []

    config_path = find_config_path(config)
    if not config_path.is_file():
        results.append(
            CheckResult(
                False,
                "config.yaml",
                f"não encontrado em {config_path}. "
                "Copie config/quickstart.yaml → config/config.yaml",
            )
        )
        return results

    try:
        settings = load_settings(config_path)
        results.append(CheckResult(True, "config.yaml válido", str(config_path)))
    except Exception as exc:  # noqa: BLE001 — doctor must surface any validation error
        results.append(CheckResult(False, "config.yaml válido", str(exc)))
        return results

    # Env vars referenced by telegram
    for env_name, label in [
        (settings.telegram.api_id_env, "TG_API_ID"),
        (settings.telegram.api_hash_env, "TG_API_HASH"),
    ]:
        if os.environ.get(env_name):
            results.append(CheckResult(True, f"{label} presente", env_name))
        else:
            results.append(
                CheckResult(
                    True,
                    f"{label} presente",
                    f"ausente ({env_name}) — necessário a partir do login (Sprint 3)",
                    warn=True,
                )
            )

    # Catalog + watch models
    try:
        catalog = load_gpu_catalog()
        index = ModelIndex(catalog)
        results.append(
            CheckResult(True, "catálogo GPU", f"{len(catalog.products)} modelos")
        )
    except Exception as exc:  # noqa: BLE001
        results.append(CheckResult(False, "catálogo GPU", str(exc)))
        return results

    missing: list[str] = []
    for rule in settings.watch:
        if not rule.models:
            continue
        for name in rule.models:
            hit = index.resolve(name)
            if hit is None and name not in catalog.products:
                missing.append(name)
    if missing:
        results.append(
            CheckResult(
                False,
                "modelos do watch no catálogo",
                "não encontrados: " + ", ".join(missing),
            )
        )
    else:
        n = sum(len(r.models or []) for r in settings.watch)
        results.append(CheckResult(True, "modelos do watch no catálogo", f"{n} ok"))

    # Storage path / migrate
    try:
        db_path = Path(settings.storage.path)
        conn = connect(db_path)
        ver = user_version(conn)
        conn.close()
        results.append(
            CheckResult(True, "SQLite + migrations", f"{db_path} (user_version={ver})")
        )
    except Exception as exc:  # noqa: BLE001
        results.append(CheckResult(False, "SQLite + migrations", str(exc)))

    if not settings.watch:
        results.append(
            CheckResult(False, "watch rules", "nenhuma regra em watch — nada será alertado")
        )
    else:
        results.append(CheckResult(True, "watch rules", f"{len(settings.watch)} regra(s)"))

    # Session file (informational until Sprint 3)
    session = Path(settings.telegram.session)
    if session.is_file():
        results.append(CheckResult(True, "arquivo de sessão", str(session)))
    else:
        results.append(
            CheckResult(
                True,
                "arquivo de sessão",
                f"ainda não existe ({session}) — esperado até `garimpo login`",
                warn=True,
            )
        )

    return results


def format_results(results: list[CheckResult]) -> str:
    lines: list[str] = []
    for r in results:
        if r.ok and r.warn:
            mark = "⚠"
        elif r.ok:
            mark = "✓"
        else:
            mark = "✗"
        detail = f" — {r.detail}" if r.detail else ""
        lines.append(f"{mark} {r.label}{detail}")
    return "\n".join(lines)


def exit_code(results: list[CheckResult]) -> int:
    # warnings (ok=True, warn=True) don't fail; hard failures do
    return 1 if any(not r.ok for r in results) else 0
