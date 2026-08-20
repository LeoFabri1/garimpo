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
