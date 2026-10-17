from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="WEAVE_", env_file=Path(__file__).resolve().parents[2] / ".env",
        extra="ignore",
    )
    graph_mode: Literal["fixture", "falkordb"] = "falkordb"
    graph_name: str = "novapay"
    graph_factory: str = ""
    source_backend: Literal["delegate", "weave_data"] = "delegate"
    falkordb_host: str = "localhost"
    falkordb_port: int = Field(default=6379, ge=1, le=65535)
    falkordb_username: str | None = None
    falkordb_password: SecretStr | None = None
    falkordb_ssl: bool = False
    llm_provider: Literal["none", "ollama", "openrouter"] = "none"
    openrouter_api_key: SecretStr | None = Field(default=None, repr=False, validation_alias=AliasChoices(
        "WEAVE_OPENROUTER_API_KEY", "OPENROUTER_API_KEY", "openrouter_api_key"))
    llm_model: Literal["openai/gpt-oss-120b"] = Field(default="openai/gpt-oss-120b", validation_alias=AliasChoices(
        "WEAVE_LLM_MODEL", "LLM_MODEL", "llm_model"))
    openrouter_max_tokens: int = Field(default=1200, ge=256, le=4096)
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    llm_timeout_seconds: float = Field(default=30, gt=0, le=90)
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
