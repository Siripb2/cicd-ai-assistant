"""
Centralized application configuration.

All runtime configuration is sourced from environment variables (12-factor
app principle). Never hardcode secrets or environment-specific values
anywhere else in the codebase — import `settings` instead.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- App ---
    app_name: str = "CI/CD AI Assistant"
    environment: str = "development"  # development | staging | production
    log_level: str = "INFO"

    # --- Database ---
    database_url: str = "sqlite:///./pipeline_analysis.db"

    # --- Gemini / LLM ---
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"
    gemini_temperature: float = 0.2
    gemini_max_output_tokens: int = 1024
    gemini_timeout_seconds: float = 20.0
    gemini_max_retries: int = 3
    gemini_max_total_wait_seconds: float = 45.0

    # --- Log handling ---
    max_log_chars: int = 8000  # truncate from the tail (most recent = most relevant)

    # --- GitHub integration ---
    github_token: str = ""  # used by the *consumer* workflow, not required by this service itself

    # --- Security ---
    api_key: str = ""  # shared-secret auth for inbound requests (see app/core/security.py)

    # --- Pagination ---
    default_page_size: int = 20
    max_page_size: int = 100


@lru_cache
def get_settings() -> Settings:
    """Settings are cached for the process lifetime; tests override via env vars."""
    return Settings()


settings = get_settings()
