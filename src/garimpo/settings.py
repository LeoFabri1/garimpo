"""Pydantic v2 settings loaded from YAML (+ env for secrets)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

from garimpo import DEFAULT_APP_VERSION


class TelegramSettings(BaseModel):
    backend: Literal["telethon", "pyrotgfork"] = "telethon"
    api_id_env: str = "TG_API_ID"
    api_hash_env: str = "TG_API_HASH"
    session: str = "data/session.session"
    session_string_env: str | None = None
    device_model: str = "Desktop"
    system_version: str = "Linux 6.8"
    app_version: str = DEFAULT_APP_VERSION


class SourceRef(BaseModel):
    username: str | None = None
    id: int | None = None
    parser: str = "generic"
    enabled: bool = True

    @model_validator(mode="before")
    @classmethod
    def from_string(cls, data: Any) -> Any:
        if isinstance(data, str):
            return {"username": data.lstrip("@"), "enabled": True}
        return data


class CatalogSettings(BaseModel):
    extra_paths: list[str] = Field(default_factory=list)


class WatchRuleConfig(BaseModel):
    name: str | None = None
    category: str = "gpu"
    models: list[str] | None = None
    perf_tier: str | None = None  # e.g. ">=97"
    max_price: float
    max_price_per_perf: float | None = None
    condition: list[str] = Field(default_factory=lambda: ["new"])
    stores_exclude: list[str] = Field(default_factory=list)
    # Overrides alerts.<level>.silent for this rule's alerts; a rule set to
    # false also skips quiet hours. None keeps the level's setting.
    silent: bool | None = None
    # Every offer that passes the filters and sits under max_price alerts
    # (at least NORMAL), whatever the percentile says; also skips the rate
    # limit. For a hunt where the ceiling IS the decision.
    always_alert: bool = False
    # Also ring the siren (alerts.siren, Bark critical push) for this rule.
    siren: bool = False


class ScoringSettings(BaseModel):
    window_days: int = 90
    half_life_days: float = 21.0
    min_samples: int = 12
    outlier_mad_threshold: float = 3.0


class AlertLevelSettings(BaseModel):
    percentile: float = 0.15
    silent: bool = True
    quiet_hours: list[int] | None = None
    min_store_trust: float | None = None

    @field_validator("percentile")
    @classmethod
    def pct_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"percentile deve estar entre 0 e 1, recebido {v}")
        return v


class BotSettings(BaseModel):
    token_env: str = "TG_BOT_TOKEN"
    chat_id_env: str = "TG_CHAT_ID"


class WebhookSettings(BaseModel):
    url_env: str = "WEBHOOK_URL"


class SirenSettings(BaseModel):
    key_env: str = "BARK_KEY"
    server: str = "https://api.day.app"


class AlertsSettings(BaseModel):
    channel: Literal["saved_messages", "bot", "webhook", "console"] = "console"
    bot: BotSettings | None = None
    webhook: WebhookSettings | None = None
    # Extra loud push for rules with `siren: true`; fires next to `channel`.
    siren: SirenSettings | None = None
    critical: AlertLevelSettings = Field(
        default_factory=lambda: AlertLevelSettings(
            percentile=0.03, silent=False, min_store_trust=0.9
        )
    )
    normal: AlertLevelSettings = Field(
        default_factory=lambda: AlertLevelSettings(percentile=0.15, silent=True)
    )
    cooldown_hours: float = 6.0
    cooldown_override_drop: float = 0.03
    max_per_hour: int = 8

    @model_validator(mode="after")
    def critical_stricter(self) -> AlertsSettings:
        if self.critical.percentile >= self.normal.percentile:
            raise ValueError(
                "alerts.critical.percentile deve ser < alerts.normal.percentile"
            )
        return self


class StorageSettings(BaseModel):
    path: str = "data/garimpo.db"
    retention_raw_days: int = 30


class HealthSettings(BaseModel):
    heartbeat_url_env: str | None = None
    interval_minutes: int = 5
    # Silêncio maior que isto em TODAS as fontes é tratado como conexão morta
    # e dispara recuperação. Sete canais de oferta fazem ~37 mensagens/hora,
    # então 30 min de nada já é anormal; de madrugada pode ser legítimo, e o
    # custo de uma varredura à toa é um fetch por fonte devolvendo zero.
    stale_ingest_minutes: int = 30
    # Linha periódica de "estou vivo, vi isto". 81% do tráfego é triaged_out e
    # vai para DEBUG, então em INFO o log fica parado por horas e um daemon
    # saudável parece morto.
    pulse_minutes: float = 15.0


class LoggingSettings(BaseModel):
    level: str = "INFO"
    format: Literal["console", "json"] = "console"


class Settings(BaseModel):
    telegram: TelegramSettings = Field(default_factory=TelegramSettings)
    sources: list[SourceRef] = Field(default_factory=list)
    catalog: CatalogSettings = Field(default_factory=CatalogSettings)
    watch: list[WatchRuleConfig] = Field(default_factory=list)
    scoring: ScoringSettings = Field(default_factory=ScoringSettings)
    alerts: AlertsSettings = Field(default_factory=AlertsSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    health: HealthSettings = Field(default_factory=HealthSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)

    @model_validator(mode="before")
    @classmethod
    def _empty_section_means_default(cls, data: Any) -> Any:
        """`health:` sem nada embaixo é YAML válido e vira None.

        Comentar o conteúdo de um bloco e deixar a chave é o jeito natural de
        desligar uma seção, e devolvia um erro de pydantic que falava em
        "Input should be a valid dictionary" sem dizer qual seção nem que ela
        estava vazia. Chave presente e vazia significa "use os padrões".

        Vale para todas: `sources:` vazio já tem `[]` como padrão, então
        descartar dá o mesmo resultado que tratar como lista vazia.
        """
        if not isinstance(data, dict):
            return data
        return {k: v for k, v in data.items() if v is not None}

    def env(self, name: str) -> str | None:
        value = os.environ.get(name)
        return value if value not in (None, "") else None


def find_config_path(explicit: Path | None = None) -> Path:
    if explicit is not None:
        return explicit
    candidates = [
        Path("config/config.yaml"),
        Path("config/quickstart.yaml"),
    ]
    for path in candidates:
        if path.is_file():
            return path
    return candidates[0]


def load_settings(path: Path | None = None) -> Settings:
    config_path = find_config_path(path)
    if not config_path.is_file():
        raise FileNotFoundError(
            f"Config não encontrada: {config_path}. "
            "Copie config/quickstart.yaml para config/config.yaml"
        )
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return Settings.model_validate(raw)
