"""Logout must revoke server-side, not just forget locally.

Deleting the session file leaves the device authorized on Telegram, which is
the opposite of what someone typing "logout" wants.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from garimpo.auth.logout import run_logout
from garimpo.settings import Settings


def _settings(tmp_path: Path) -> Settings:
    return Settings.model_validate(
        {
            "telegram": {"session": str(tmp_path / "session.session")},
            "watch": [{"name": "t", "category": "gpu", "max_price": 6000}],
            "storage": {"path": str(tmp_path / "g.db")},
        }
    )


@pytest.mark.asyncio
async def test_no_session_is_a_no_op(tmp_path: Path) -> None:
    result = await run_logout(_settings(tmp_path))
    assert not result.revoked
    assert not result.file_removed
    assert "Nenhuma sessão local" in result.detail


@pytest.mark.asyncio
async def test_local_only_removes_file_but_warns_session_lives(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    session = Path(settings.telegram.session)
    session.write_bytes(b"fake session")

    result = await run_logout(settings, local_only=True)

    assert result.file_removed
    assert not session.exists()
    assert not result.revoked, "local-only must not claim a revocation"
    assert "SEGUE ATIVA" in result.detail, "the user must know it is not revoked"


@pytest.mark.asyncio
async def test_local_only_also_clears_sqlite_sidecars(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    session = Path(settings.telegram.session)
    session.write_bytes(b"fake session")
    sidecar = session.with_suffix(session.suffix + "-journal")
    sidecar.write_bytes(b"journal")

    await run_logout(settings, local_only=True)

    assert not session.exists()
    assert not sidecar.exists(), "a leftover journal can resurrect session state"
