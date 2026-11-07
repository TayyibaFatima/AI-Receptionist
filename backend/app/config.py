"""Reads settings from environment variables (and backend/.env). No secrets live in code."""

import os
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
# utf-8-sig tolerates the BOM some Windows editors add; real env vars always win.
load_dotenv(ENV_PATH, encoding="utf-8-sig")


class Settings:
    def __init__(self) -> None:
        self.database_url: str = self._normalize_db_url(os.getenv("DATABASE_URL", ""))
        self.groq_api_key: str = os.getenv("GROQ_API_KEY", "")
        self.groq_model: str = os.getenv("GROQ_MODEL", "")
        self.clinic_name: str = os.getenv("CLINIC_NAME", "Luméra Aesthetics")
        self.clinic_timezone: str = os.getenv("CLINIC_TIMEZONE", "Asia/Karachi")
        self.frontend_url: str = os.getenv("FRONTEND_URL", "http://localhost:5173")
        self.chat_rate_limit_per_minute: int = int(os.getenv("CHAT_RATE_LIMIT_PER_MINUTE", "20"))

    @staticmethod
    def _normalize_db_url(url: str) -> str:
        """Hosts often give 'postgres://' or 'postgresql://'; SQLAlchemy needs the psycopg 3 driver name."""
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+psycopg://", 1)
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url

    @property
    def timezone(self) -> ZoneInfo:
        return ZoneInfo(self.clinic_timezone)

    @property
    def cors_origins(self) -> list[str]:
        origins = {o.strip().rstrip("/") for o in self.frontend_url.split(",") if o.strip()}
        origins |= {"http://localhost:5173", "http://127.0.0.1:5173"}
        return sorted(origins)


@lru_cache
def get_settings() -> Settings:
    return Settings()
