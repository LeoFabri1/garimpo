"""`garimpo daemon` — três comandos launchctl viraram um.

Subir o daemon exigia copiar um plist com caminhos absolutos de outra máquina,
lembrar de `unload` antes de `load` (senão "Load failed: 5", que soa como erro
de permissão e não é), e saber onde ficava o log.
"""

from __future__ import annotations

import platform
from pathlib import Path

import pytest

from garimpo.tools import daemon


def test_generated_plist_uses_this_machine(tmp_path: Path, monkeypatch) -> None:
    """O deploy/ tinha caminhos absolutos de uma máquina só."""
    if platform.system() != "Darwin":
        pytest.skip("launchd é macOS")
    home = tmp_path / "home"
    (home / "Library" / "LaunchAgents").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.chdir(Path.cwd())

    plist = daemon.install(Path("config/quickstart.yaml"))
    texto = plist.read_text()
    assert str(Path.cwd().resolve()) in texto, "WorkingDirectory precisa ser real"
    assert "quickstart.yaml" in texto
    assert "PYTHONUNBUFFERED" in texto, "sem isto o log congela e parece daemon morto"
    assert "caffeinate" in texto


def test_install_refuses_without_the_binary(tmp_path: Path, monkeypatch) -> None:
    if platform.system() != "Darwin":
        pytest.skip("launchd é macOS")
    home = tmp_path / "home"
    (home / "Library" / "LaunchAgents").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr(daemon.sys, "executable", str(tmp_path / "vazio" / "python"))
    with pytest.raises(FileNotFoundError, match="uv sync"):
        daemon.install(Path("config/quickstart.yaml"))


def test_stop_is_idempotent(monkeypatch) -> None:
    """Parar o que já está parado não é erro — era `Unload failed: 5`."""
    monkeypatch.setattr(daemon, "is_loaded", lambda: False)
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    assert daemon.stop() is False


def test_linux_points_at_systemd(monkeypatch) -> None:
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    with pytest.raises(daemon.UnsupportedPlatformError, match="systemctl"):
        daemon.start()


def test_other_platforms_say_what_to_do_instead(monkeypatch) -> None:
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    with pytest.raises(daemon.UnsupportedPlatformError, match="garimpo run"):
        daemon.start()


def test_log_path_follows_the_database(tmp_path: Path) -> None:
    p = daemon.paths(Path("config/quickstart.yaml"))
    assert p.log.name == "garimpo.log"
    assert p.plist.name.endswith(".plist")


# --- Ruído de biblioteca e crescimento de log ------------------------------
# 146 das 170 linhas do err log eram INFO do Telethon narrando handshake, e o
# que importa — FloodWait, erro de conexão — ficava enterrado.


def test_noisy_libraries_are_quiet_at_info() -> None:
    import logging as _logging

    from garimpo.logging import configure_logging

    configure_logging(level="INFO", fmt="json")
    assert _logging.getLogger("telethon").level == _logging.WARNING


def test_debug_restores_library_verbosity() -> None:
    """O nível fica no objeto logger: só pular o silenciamento não bastava."""
    import logging as _logging

    from garimpo.logging import configure_logging

    configure_logging(level="INFO", fmt="json")
    configure_logging(level="DEBUG", fmt="json")
    assert _logging.getLogger("telethon").level == _logging.NOTSET
    configure_logging(level="INFO", fmt="json")  # não vaza para os outros testes


def test_rotation_only_fires_above_the_cap(tmp_path: Path, monkeypatch) -> None:
    p = daemon.Paths(
        plist=tmp_path / "x.plist",
        log=tmp_path / "garimpo.log",
        errlog=tmp_path / "garimpo.err.log",
    )
    monkeypatch.setattr(daemon, "paths", lambda config=None: p)
    p.log.write_bytes(b"x" * 100)
    p.errlog.write_bytes(b"y" * 5000)

    assert daemon.rotate_logs(max_bytes=1000) == [p.errlog.with_suffix(".log.1")]
    assert p.log.read_bytes() == b"x" * 100, "log pequeno fica intacto"
    assert not p.errlog.exists(), "o grande foi renomeado"


def test_rotation_keeps_only_one_previous(tmp_path: Path, monkeypatch) -> None:
    p = daemon.Paths(
        plist=tmp_path / "x.plist",
        log=tmp_path / "garimpo.log",
        errlog=tmp_path / "garimpo.err.log",
    )
    monkeypatch.setattr(daemon, "paths", lambda config=None: p)
    for _ in range(3):
        p.log.write_bytes(b"z" * 5000)
        daemon.rotate_logs(max_bytes=1000)
    assert not list(tmp_path.glob("*.log.2")), "não acumula gerações"
