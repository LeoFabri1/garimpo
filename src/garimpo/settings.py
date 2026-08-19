"""Pydantic v2 settings loaded from YAML (+ env for secrets)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator


class TelegramSettings(BaseModel):
    backend: Literal["telethon", "pyrotgfork"] = "telethon"
    api_id_env: str = "TG_API_ID"
    api_hash_env: str = "TG_API_HASH"
    session: str = "data/session.session"
    session_string_env: str | None = None
    device_model: str = "Desktop"
    system_version: str = "Linux 6.8"
    app_version: str = "garimpo 0.0.1"


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


class AlertsSettings(BaseModel):
    channel: Literal["saved_messages", "bot", "webhook", "console"] = "console"
    bot: BotSettings | None = None
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


class LlmSettings(BaseModel):
    enabled: bool = False
    provider: str = "openai_compatible"
    base_url: str = "https://api.groq.com/openai/v1"
    model: str = "llama-3.3-70b-versatile"
    api_key_env: str = "GROQ_API_KEY"
    only_on_parse_failure: bool = True
    max_attempts: int = 3
    timeout_s: float = 20.0


class StorageSettings(BaseModel):
    path: str = "data/garimpo.db"
    retention_raw_days: int = 30


class HealthSettings(BaseModel):
    heartbeat_url_env: str | None = None
    interval_minutes: int = 5


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
    llm: LlmSettings = Field(default_factory=LlmSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    health: HealthSettings = Field(default_factory=HealthSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)

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
