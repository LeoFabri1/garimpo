"""Build MTProto client from settings."""

from __future__ import annotations

from garimpo.auth.login import credentials_from_settings, load_dotenv_if_present
from garimpo.ingest.base import MTProtoClient
from garimpo.settings import Settings


def build_client(settings: Settings) -> MTProtoClient:
    load_dotenv_if_present()
    backend = settings.telegram.backend
    if backend == "telethon":
        from garimpo.ingest.clients.telethon_client import TelethonClient

        api_id, api_hash = credentials_from_settings(settings)
        session_string = None
        if settings.telegram.session_string_env:
            session_string = settings.env(settings.telegram.session_string_env)
        return TelethonClient(
            session=settings.telegram.session,
            api_id=api_id,
            api_hash=api_hash,
            device_model=settings.telegram.device_model,
            system_version=settings.telegram.system_version,
            app_version=settings.telegram.app_version,
            session_string=session_string,
        )
    if backend == "pyrotgfork":
        from garimpo.ingest.clients.pyro_client import PyroClient

        api_id, api_hash = credentials_from_settings(settings)
        session_string = None
        if settings.telegram.session_string_env:
            session_string = settings.env(settings.telegram.session_string_env)
        return PyroClient(
            session=settings.telegram.session,
            api_id=api_id,
            api_hash=api_hash,
            device_model=settings.telegram.device_model,
            system_version=settings.telegram.system_version,
            app_version=settings.telegram.app_version,
            session_string=session_string,
        )
    raise ValueError(f"backend não suportado: {backend}")
