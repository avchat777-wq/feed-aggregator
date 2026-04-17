"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://feedagg:feedagg_pass@db:5432/feed_aggregator"
    database_url_sync: str = "postgresql://feedagg:feedagg_pass@db:5432/feed_aggregator"

    # ── App ───────────────────────────────────────────────────────────────────
    app_secret_key: str = "change-me-to-random-string-64-chars"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    feed_output_dir: str = "/app/static/feed"
    feed_base_url: str = "http://localhost:8080/feed"

    # ── Feed cache ────────────────────────────────────────────────────────────
    # Directory where raw feed files are cached (one sub-folder per source).
    # Used as fallback when the source is temporarily unavailable.
    feed_cache_dir: str = "/app/cache"

    # ── Scheduler ─────────────────────────────────────────────────────────────
    sync_interval_hours: int = 4

    # ── Telegram ──────────────────────────────────────────────────────────────
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None

    # ── Thresholds (all configurable via .env) ────────────────────────────────
    threshold_drop_warning: int = 20      # % change in object count → WARNING
    threshold_drop_critical: int = 50     # % change in object count → reject update
    threshold_price_change_pct: int = 15  # % of objects with price change → WARNING
    threshold_price_change_min: int = 10  # min single-object % price change to count
    threshold_source_fail_count: int = 2  # consecutive failures → CRITICAL alert

    # ── Pre-flight diagnostics ────────────────────────────────────────────────
    # Timeout used specifically during pre-flight checks (seconds).
    # Separate from http_timeout so we can abort slow sources early.
    preflight_timeout_s: int = 5

    # ── Auth ──────────────────────────────────────────────────────────────────
    admin_username: str = "admin"
    admin_password: str = "change-me"
    access_token_expire_minutes: int = 480  # 8 hours

    # ── Feed HTTP ─────────────────────────────────────────────────────────────
    feed_serve_port: int = 8080

    # ── HTTP client ───────────────────────────────────────────────────────────
    http_timeout: int = 60  # seconds (used for full feed downloads)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
