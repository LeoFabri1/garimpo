"""Warnings shown before login / in docs (DESIGN §22)."""

from __future__ import annotations

from garimpo.auth.errors import LoginAborted

USERBOT_RISK_BANNER = """
╔══════════════════════════════════════════════════════════════════╗
║  AVISO — USERBOT / RISCO DE BANIMENTO                            ║
╠══════════════════════════════════════════════════════════════════╣
║  O Garimpo NÃO usa bot do BotFather.                             ║
║  Ele autentica como CONTA DE USUÁRIO (MTProto) e lê grupos.      ║
║                                                                  ║
║  Isso é zona cinza no ToS do Telegram. Existe risco real de      ║
║  restrição ou BANIMENTO do NÚMERO usado neste login.             ║
║                                                                  ║
║  USE UM NÚMERO SECUNDÁRIO — nunca o Telegram principal           ║
║  (trabalho, família, banco, 2FA).                                ║
║                                                                  ║
║  O cliente só LÊ os grupos (não envia, não reage, não marca      ║
║  como lido). A escrita, se houver, é só para você                ║
║  (Saved Messages / bot próprio).                                 ║
║                                                                  ║
║  Continuando, você declara que entendeu o risco.                 ║
╚══════════════════════════════════════════════════════════════════╝
""".strip()

CONFIRM_PROMPT = (
    'Digite "secundario" (sem aspas) para continuar com este login,\n'
    "ou Ctrl+C para cancelar: "
)
CONFIRM_TOKEN = "secundario"


def confirm_userbot_risk(*, skip: bool = False) -> None:
    """Print ban warning and require explicit acknowledgement before login."""
    print(USERBOT_RISK_BANNER)
    print()
    if skip:
        print("(confirmação de risco ignorada via --i-understand)")
        return
    answer = input(CONFIRM_PROMPT).strip().lower()
    if answer != CONFIRM_TOKEN:
        raise LoginAborted(
            "Login cancelado. Use um número secundário e rode de novo quando "
            "estiver ciente do risco.\n"
            'É preciso digitar exatamente: secundario'
        )
