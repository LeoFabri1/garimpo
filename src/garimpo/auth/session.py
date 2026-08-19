"""Session path helpers and StringSession export."""

from __future__ import annotations

from pathlib import Path


def session_path(configured: str) -> Path:
    """Fixed session path from config — never random (DESIGN §20.2)."""
    path = Path(configured)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def ensure_session_permissions(path: Path) -> None:
    if path.is_file():
        path.chmod(0o600)


SESSION_STRING_WARNING = """\
⚠️  Esta string dá acesso TOTAL à sua conta Telegram.
    Quem tiver ela lê suas mensagens e age como você.

    • guarde como secret/variável de ambiente, nunca em arquivo commitado
    • se vazar, revogue em: Telegram → Configurações → Dispositivos
    • esta string não será exibida de novo
"""
