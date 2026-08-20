"""Controle do daemon em background, sem decorar launchctl.

Rodar o Garimpo 24/7 exigia copiar um plist à mão, lembrar de `unload` antes de
`load` (senão vem "Load failed: 5"), e saber onde fica o log. Três comandos e
um arquivo com caminhos absolutos que só serviam para uma máquina.
"""

from __future__ import annotations

import platform
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

LABEL = "com.garimpo.daemon"

_PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" \
"http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<!-- Gerado por `garimpo daemon install`. Editar à mão é possível; regerar
     sobrescreve. -->
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{label}</string>

    <!-- caffeinate envelopa o daemon: com um utilitário como argumento, as
         assertions valem enquanto ele estiver de pé. Não vence tampa fechada;
         para isso o watchdog de ingestão recupera ao acordar. -->
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/caffeinate</string>
        <string>-ims</string>
        <string>{binario}</string>
        <string>run</string>
        <string>-c</string>
        <string>{config}</string>
    </array>

    <key>WorkingDirectory</key>
    <string>{cwd}</string>

    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>ThrottleInterval</key>
    <integer>30</integer>

    <!-- Python bufferiza stdout em blocos de 8KB quando a saída é arquivo: sem
         isto o log congela por horas e `tail -f` parece um daemon morto. -->
    <key>EnvironmentVariables</key>
    <dict>
        <key>PYTHONUNBUFFERED</key>
        <string>1</string>
    </dict>

    <key>StandardOutPath</key>
    <string>{log}</string>
    <key>StandardErrorPath</key>
    <string>{errlog}</string>

    <key>ProcessType</key>
    <string>Background</string>
    <key>LowPriorityIO</key>
    <true/>
</dict>
</plist>
"""


class UnsupportedPlatformError(RuntimeError):
    def __init__(self, sistema: str) -> None:
        if sistema == "Linux":
            msg = (
                "`garimpo daemon` cobre macOS (launchd). No Linux use systemd:\n"
                "  sudo cp garimpo.service /etc/systemd/system/\n"
                "  sudo systemctl enable --now garimpo\n"
                "  journalctl -u garimpo -f"
            )
        else:
            msg = f"`garimpo daemon` não suporta {sistema}. Rode `garimpo run` direto."
        super().__init__(msg)


@dataclass(frozen=True)
class Paths:
    plist: Path
    log: Path
    errlog: Path


def paths(config: Path | None = None) -> Paths:
    from garimpo.settings import find_config_path, load_settings

    cfg = find_config_path(config)
    db = Path(load_settings(cfg).storage.path)
    base = db.parent if db.parent != Path("") else Path("data")
    return Paths(
        plist=Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist",
        log=(base / "garimpo.log").resolve(),
        errlog=(base / "garimpo.err.log").resolve(),
    )


def _require_macos() -> None:
    sistema = platform.system()
    if sistema != "Darwin":
        raise UnsupportedPlatformError(sistema)


def _launchctl(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["launchctl", *args], capture_output=True, text=True, check=False
    )


def is_loaded() -> bool:
    out = _launchctl("list").stdout
    return any(LABEL in line for line in out.splitlines())


def pid() -> int | None:
    for line in _launchctl("list").stdout.splitlines():
        if LABEL in line:
            campo = line.split("\t", 1)[0].strip()
            return int(campo) if campo.isdigit() else None
    return None


def install(config: Path | None = None) -> Path:
    """Gera o plist com os caminhos desta máquina.

    O arquivo em deploy/ tinha caminhos absolutos de uma máquina só — servia de
    referência e não de instalação.
    """
    _require_macos()
    from garimpo.settings import find_config_path

    p = paths(config)
    binario = Path(sys.executable).parent / "garimpo"
    if not binario.exists():
        raise FileNotFoundError(
            f"binário do garimpo não encontrado em {binario}. "
            "Rode `uv sync` e tente de novo."
        )
    p.plist.parent.mkdir(parents=True, exist_ok=True)
    p.plist.write_text(
        _PLIST.format(
            label=LABEL,
            binario=binario,
            config=find_config_path(config).resolve(),
            cwd=Path.cwd().resolve(),
            log=p.log,
            errlog=p.errlog,
        ),
        encoding="utf-8",
    )
    return p.plist


MAX_LOG_BYTES = 20 * 1024 * 1024


def rotate_logs(config: Path | None = None, *, max_bytes: int = MAX_LOG_BYTES) -> list[Path]:
    """Roda no start, com o daemon parado — nunca com o log aberto.

    `StandardOutPath` do launchd só acrescenta, e não rotaciona. Sete canais
    ativos produzem na casa de centenas de KB por dia, o que vira gigabytes
    num daemon que roda o ano inteiro.

    Truncar por fora enquanto o daemon está de pé não funciona: o launchd
    segura o descritor, o offset continua onde estava e o resultado é um
    arquivo esparso. Por isso a rotação acontece aqui, entre o stop e o start.
    Um daemon que nunca reinicia nunca rotaciona — limitação aceita, e o
    motivo de o limite ser generoso.
    """
    girados: list[Path] = []
    p = paths(config)
    for log in (p.log, p.errlog):
        if log.is_file() and log.stat().st_size > max_bytes:
            anterior = log.with_suffix(log.suffix + ".1")
            anterior.unlink(missing_ok=True)
            log.rename(anterior)
            girados.append(anterior)
    return girados


def stop(config: Path | None = None) -> bool:
    """Descarrega. Idempotente: já parado não é erro."""
    _require_macos()
    if not is_loaded():
        return False
    _launchctl("unload", str(paths(config).plist))
    return True


def start(config: Path | None = None) -> None:
    _require_macos()
    rotate_logs(config)
    p = paths(config)
    if not p.plist.is_file():
        install(config)
    resultado = _launchctl("load", "-w", str(p.plist))
    if resultado.returncode != 0 and not is_loaded():
        raise RuntimeError(resultado.stderr.strip() or "launchctl load falhou")


def restart(config: Path | None = None) -> None:
    """O que o usuário quer 90% das vezes: releu o config, quer aplicar.

    `load` sobre um agente já carregado devolve "Load failed: 5", que soa como
    erro de permissão e não é.
    """
    stop(config)
    start(config)
