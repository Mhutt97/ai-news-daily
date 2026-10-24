"""Configuration loader for AI News Daily."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DIGESTS_DIR = PROJECT_ROOT / "digests"


def load_dotenv_file(env_path: Path) -> None:
    """Lightweight .env file loader with zero external dependencies."""
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


@dataclass
class Settings:
    """Application settings loaded from environment variables or .env."""

    gemini_api_key: str
    gemini_model: str
    discord_webhook_url: str
    resend_api_key: str
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    email_from: str
    email_to: str
    dashboard_url: str
    lookback_hours: int
    max_items_per_source: int

    @classmethod
    def from_env(cls, lookback_override: int | None = None) -> Settings:
        load_dotenv_file(PROJECT_ROOT / ".env")
        return cls(
            gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip(),
            discord_webhook_url=os.getenv("DISCORD_WEBHOOK_URL", "").strip(),
            resend_api_key=os.getenv("RESEND_API_KEY", "").strip(),
            smtp_host=os.getenv("SMTP_HOST", "smtp.gmail.com").strip(),
            smtp_port=int(os.getenv("SMTP_PORT", "587").strip() or "587"),
            smtp_user=os.getenv("SMTP_USER", "").strip(),
            smtp_password=os.getenv("SMTP_PASSWORD", "").strip(),
            email_from=os.getenv("EMAIL_FROM", "").strip(),
            email_to=os.getenv("EMAIL_TO", "").strip(),
            dashboard_url=os.getenv(
                "DASHBOARD_URL", "https://mhutt97.github.io/ai-news-daily/"
            ).strip(),
            lookback_hours=lookback_override
            if lookback_override is not None
            else int(os.getenv("LOOKBACK_HOURS", "24").strip() or "24"),
            max_items_per_source=int(
                os.getenv("MAX_ITEMS_PER_SOURCE", "5").strip() or "5"
            ),
        )

    @property
    def has_discord(self) -> bool:
        return bool(self.discord_webhook_url)

    @property
    def has_email(self) -> bool:
        has_resend = bool(self.resend_api_key and self.email_to)
        has_smtp = bool(
            self.smtp_host and self.smtp_user and self.smtp_password and self.email_to
        )
        return has_resend or has_smtp
