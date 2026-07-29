"""Environment-driven application settings.

Everything the app needs to know about its own configuration lives here.
Nothing else in the codebase should touch `os.environ` directly - import
`settings` instead. That gives us one place to look when a deployment
behaves differently than expected, and makes it trivial to override
values in tests via env vars or a `.env` file.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed, validated application configuration.

    Values are resolved in the usual pydantic-settings order: process
    environment variables first, then a local `.env` file, then the
    defaults declared below.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # General
    app_name: str = "Healthcare AI Chatbot"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = True
    log_level: str = "INFO"

    # LLM provider (see app/llm.py for the abstraction that consumes these)
    llm_provider: Literal["openai", "gemini"] = "openai"

    openai_api_key: Optional[str] = Field(default=None)
    openai_model: str = "gpt-5"
    openai_fallback_model: str = "gpt-4.1"

    gemini_api_key: Optional[str] = Field(default=None)
    gemini_model: str = "gemini-2.5-flash"

    llm_temperature: float = 0.3
    llm_max_tokens: int = 700
    llm_timeout_seconds: int = 30
    llm_max_retries: int = 3

    # RAG / vector store
    embedding_model_name: str = "all-MiniLM-L6-v2"
    vectorstore_dir: Path = Path("vectorstore")
    knowledge_base_dir: Path = Path("knowledge_base/docs")
    rag_top_k: int = 4
    chunk_size: int = 500
    chunk_overlap: int = 75
    rag_enabled: bool = True

    # Conversation memory
    max_memory_turns: int = 10

    # API server
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_allow_origins: str = "*"

    # Guardrails
    enable_guardrails: bool = True

    @field_validator("llm_temperature")
    @classmethod
    def _temperature_in_range(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            raise ValueError("llm_temperature must be between 0.0 and 1.0")
        return value

    @model_validator(mode="after")
    def _overlap_smaller_than_chunk(self) -> "Settings":
        # A chunk overlap >= chunk_size would stall the RAG chunker's
        # sliding window (the step size would never advance past zero).
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        """CORS origins as a list, ready for FastAPI's CORSMiddleware."""
        return [origin.strip() for origin in self.cors_allow_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Process-wide cached Settings instance."""
    return Settings()


settings = get_settings()
