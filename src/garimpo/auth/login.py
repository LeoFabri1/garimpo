"""Interactive Telegram login with FloodWait protection."""

from __future__ import annotations

import os
import re
from pathlib import Path

from garimpo.auth.errors import LoginAborted, LoginConfigError
from garimpo.auth.session import (
    SESSION_STRING_WARNING,
    ensure_session_permissions,
    session_path,
)
from garimpo.settings import Settings

MAX_ATTEMPTS = 3

_API_HASH_RE = re.compile(r"^[0-9a-fA-F]{32}$")


def validate_credentials(api_id: str, api_hash: str) -> tuple[int, str]:
    if not api_id.isdigit():
        raise LoginConfigError(
            f"api_id deve ser numérico, recebido {api_id!r}. "
            "Copie de https://my.telegram.org → API Development tools."
        )
    if not _API_HASH_RE.match(api_hash.strip()):
        raise LoginConfigError(
            f"api_hash deve ter 32 caracteres hex, recebido len={len(api_hash)}. "
            "Erro de cópia detectado localmente — tentativa NÃO enviada ao Telegram."
        )
    return int(api_id), api_hash.strip()


def credentials_from_settings(settings: Settings) -> tuple[int, str]:
    api_id = settings.env(settings.telegram.api_id_env)
    api_hash = settings.env(settings.telegram.api_hash_env)
    if not api_id or not api_hash:
        raise LoginConfigError(
            f"Defina {settings.telegram.api_id_env} e {settings.telegram.api_hash_env} "
            "no .env (veja .env.example)."
        )
    return validate_credentials(api_id, api_hash)


async def run_login(
    settings: Settings,
    *,
    use_qr: bool = True,
    export_string: bool = False,
    phone: str | None = None,
    password: str | None = None,
    skip_risk_confirm: bool = False,
) -> str | None:
    """Perform login. Returns session string if export_string else None."""
    from garimpo.auth.warnings import confirm_userbot_risk
    from garimpo.ingest.clients.telethon_client import (
        TelethonClient,
        TelethonUnavailableError,
    )

    confirm_userbot_risk(skip=skip_risk_confirm)

    try:
        api_id, api_hash = credentials_from_settings(settings)
    except LoginConfigError:
        raise

    path = session_path(settings.telegram.session)
    attempts = 0

    while attempts < MAX_ATTEMPTS:
        attempts += 1
        try:
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
            if await tg.is_user_authorized():
                print(f"Já autenticado. Sessão: {path}")
            elif use_qr:
                from garimpo.auth.qr import login_with_qr

                await login_with_qr(tg, password=password)
            else:
                await _code_login(tg, phone=phone, password=password)

            ensure_session_permissions(path)
            me = await tg.get_me()
            phone_mask = _mask_phone(getattr(me, "phone", None))
            print(f"✓ login ok como {phone_mask}")

            exported: str | None = None
            if export_string:
                exported = await _export_string(tg)
                print(SESSION_STRING_WARNING)
                print(exported)

            await tg.disconnect()
            return exported
        except LoginConfigError:
            raise
        except TelethonUnavailableError:
            raise
        except Exception as exc:
            print(f"Tentativa {attempts}/{MAX_ATTEMPTS} falhou: {exc}")
            if attempts >= MAX_ATTEMPTS:
                raise LoginAborted(
                    "3 tentativas falharam. O Telegram bloqueia por ~22h após ~5 falhas.\n"
                    "Parando aqui para proteger sua conta.\n\n"
                    "Verifique:\n"
                    "  • o número está no formato internacional (+5519999999999)\n"
                    "  • o api_id é numérico e o api_hash tem 32 caracteres\n"
                    "  • o código chegou no app do Telegram, não por SMS\n\n"
                    "Tente de novo em alguns minutos: garimpo login"
                ) from exc
    raise LoginAborted("login abortado")


async def _code_login(client: object, *, phone: str | None, password: str | None) -> None:
    from telethon.errors import SessionPasswordNeededError

    phone = phone or input("Telefone (+5511...): ").strip()
    await client.send_code_request(phone)  # type: ignore[attr-defined]
    code = input("Código do Telegram: ").strip()
    try:
        await client.sign_in(phone, code)  # type: ignore[attr-defined]
    except SessionPasswordNeededError:
        pw = password or input("Senha 2FA: ").strip()
        await client.sign_in(password=pw)  # type: ignore[attr-defined]


async def _export_string(client: object) -> str:
    from telethon.sessions import StringSession

    return str(StringSession.save(client.session))  # type: ignore[attr-defined]


def _mask_phone(phone: str | None) -> str:
    if not phone:
        return "(sem telefone)"
    if len(phone) < 4:
        return phone
    return f"+{phone[:-4]}****" if not phone.startswith("+") else f"{phone[:-4]}****"


def load_dotenv_if_present() -> None:
    """Minimal .env loader (no dependency)."""
    path = Path(".env")
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)
