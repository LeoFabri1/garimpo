"""QR login flow — the preferred path, since it avoids SMS FloodWait."""

from __future__ import annotations

from typing import Any


async def login_with_qr(client: Any, *, password: str | None = None) -> None:
    """Show QR URL; user scans via Telegram → Devices → Connect."""
    print(
        "Lembrete: escaneie com o Telegram do NÚMERO SECUNDÁRIO "
        "(não o principal).\n"
    )
    qr_login = await client.qr_login()
    url = qr_login.url

    try:
        import qrcode

        qr = qrcode.QRCode(border=1)
        qr.add_data(url)
        qr.make(fit=True)
        qr.print_ascii(invert=True)
    except ImportError:
        # A tg:// URL cannot be scanned from a phone, so say how to fix it
        # rather than pretending this output is usable.
        print(
            "⚠ qrcode não instalado — não é possível desenhar o QR aqui.\n"
            "  Instale com: uv sync --extra telethon\n"
            "  (ou use `garimpo login --code` para login por código)\n\n"
            f"Token bruto, só útil em outro renderizador de QR:\n{url}\n"
        )

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
