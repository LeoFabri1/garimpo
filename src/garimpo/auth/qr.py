"""QR login flow (preferred path — DESIGN §20.3)."""

from __future__ import annotations

from typing import Any


async def login_with_qr(client: Any, *, password: str | None = None) -> None:
    """Show QR URL; user scans via Telegram → Devices → Connect."""
    qr_login = await client.qr_login()
    url = qr_login.url

    try:
        import qrcode

        qr = qrcode.QRCode(border=1)
        qr.add_data(url)
        qr.make(fit=True)
        qr.print_ascii(invert=True)
    except ImportError:
        print(f"QR URL (abra no Telegram → Dispositivos → Conectar):\n{url}\n")

    print(
        "Escaneie: Telegram → Configurações → Dispositivos → Conectar dispositivo"
    )

    from telethon.errors import SessionPasswordNeededError

    try:
        await qr_login.wait(timeout=180)
    except SessionPasswordNeededError:
        pw = password
        if not pw:
            pw = input("Senha 2FA: ").strip()
        await client.sign_in(password=pw)
