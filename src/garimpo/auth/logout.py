"""Session revocation.

Deleting the session file only makes *this machine* forget the session — the
device stays authorized on Telegram's side and can keep reading your account.
Revoking server-side is the part that actually matters, so that is the default
and the local file is removed only after it succeeds.
"""

from __future__ import annotations

from pathlib import Path

from garimpo.auth.session import session_path
from garimpo.settings import Settings


class LogoutResult:
    def __init__(self, *, revoked: bool, file_removed: bool, detail: str) -> None:
        self.revoked = revoked
        self.file_removed = file_removed
        self.detail = detail


def _remove_session_files(path: Path) -> bool:
    """Remove the session file and the SQLite sidecars Telethon may leave."""
    sidecars = (
        path.with_suffix(path.suffix + suffix)
        for suffix in ("-journal", "-wal", "-shm")
    )
    removed = False
    for candidate in (path, *sidecars):
        if candidate.is_file():
            candidate.unlink()
            removed = True
    return removed


async def run_logout(settings: Settings, *, local_only: bool = False) -> LogoutResult:
    path = session_path(settings.telegram.session)

    if local_only:
        removed = _remove_session_files(path)
        return LogoutResult(
            revoked=False,
            file_removed=removed,
            detail=(
                "Arquivo local removido, mas a sessão SEGUE ATIVA no Telegram. "
                "Revogue em: Telegram → Configurações → Dispositivos."
            ),
        )

    if not path.is_file():
        return LogoutResult(
            revoked=False,
            file_removed=False,
            detail=f"Nenhuma sessão local em {path} — nada a fazer.",
        )

    from garimpo.auth.login import credentials_from_settings
    from garimpo.ingest.clients.telethon_client import TelethonClient

    api_id, api_hash = credentials_from_settings(settings)
    client = TelethonClient(
        session=str(path),
        api_id=api_id,
        api_hash=api_hash,
        device_model=settings.telegram.device_model,
        system_version=settings.telegram.system_version,
        app_version=settings.telegram.app_version,
    )
    tg = client.raw
    await tg.connect()
    try:
        if not await tg.is_user_authorized():
            await tg.disconnect()
            removed = _remove_session_files(path)
            return LogoutResult(
                revoked=False,
                file_removed=removed,
                detail=(
                    "Sessão local já não autorizava (revogada em outro lugar). "
                    "Arquivo removido."
                ),
            )
        # log_out() revokes server-side; Telethon also drops the local file.
        await tg.log_out()
    finally:
        try:
            await tg.disconnect()
        except Exception:  # noqa: BLE001 — already logged out
            pass

    removed = _remove_session_files(path)
    return LogoutResult(
        revoked=True,
        file_removed=removed,
        detail=(
            "Sessão revogada no Telegram e arquivo local removido. "
            "O dispositivo desaparece de Configurações → Dispositivos."
        ),
    )
