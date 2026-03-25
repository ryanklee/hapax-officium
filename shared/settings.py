"""Typed configuration for hapax-officium.

All officium env vars validated at import time via pydantic-settings.
Feature-gated: set HAPAX_USE_SETTINGS=1 to activate in config.py.
"""

from __future__ import annotations

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class LiteLLMSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LITELLM_")

    base_url: str = Field(
        default="http://localhost:4100",
        validation_alias=AliasChoices("LITELLM_API_BASE", "LITELLM_BASE_URL"),
    )
    api_key: SecretStr = SecretStr("")


class QdrantSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="QDRANT_")

    url: str = "http://localhost:6433"


class OllamaSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OLLAMA_")

    url: str = "http://localhost:11534"


class LangfuseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LANGFUSE_")

    host: str = "http://localhost:3100"
    public_key: SecretStr = SecretStr("")
    secret_key: SecretStr = SecretStr("")


class EngineSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ENGINE_")

    enabled: bool = True
    debounce_ms: int = Field(default=200, ge=50, le=10000)
    llm_concurrency: int = Field(default=2, ge=1, le=16)
    delivery_interval_s: int = Field(default=300, ge=1)
    action_timeout_s: float = Field(default=60.0, ge=1.0)
    synthesis_enabled: bool = True
    synthesis_quiet_s: float = Field(default=180.0, ge=0.0)
    profiler_interval_s: float = Field(default=86400.0, ge=0.0)


class LogSettings(BaseSettings):
    model_config = SettingsConfigDict()

    log_level: str = Field(
        default="INFO",
        validation_alias="LOG_LEVEL",
    )
    hapax_log_human: bool = Field(
        default=False,
        validation_alias="HAPAX_LOG_HUMAN",
    )
    hapax_service: str = Field(
        default="hapax-officium",
        validation_alias="HAPAX_SERVICE",
    )


class PathSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HAPAX_")

    data_dir: str = Field(
        default="./data",
        validation_alias="HAPAX_DATA_DIR",
    )


class GovernanceSettings(BaseSettings):
    model_config = SettingsConfigDict()

    enforce_block: bool = Field(
        default=False,
        validation_alias="AXIOM_ENFORCE_BLOCK",
    )


class OfficiumSettings(BaseSettings):
    """Top-level officium configuration. Validated at import time."""

    litellm: LiteLLMSettings = Field(default_factory=LiteLLMSettings)
    qdrant: QdrantSettings = Field(default_factory=QdrantSettings)
    ollama: OllamaSettings = Field(default_factory=OllamaSettings)
    langfuse: LangfuseSettings = Field(default_factory=LangfuseSettings)
    engine: EngineSettings = Field(default_factory=EngineSettings)
    logging: LogSettings = Field(default_factory=LogSettings)
    paths: PathSettings = Field(default_factory=PathSettings)
    governance: GovernanceSettings = Field(default_factory=GovernanceSettings)
