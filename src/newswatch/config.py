"""Load settings: config/settings.yaml + config/sources.yaml + environment variables."""

import os
from pathlib import Path

import yaml
from pydantic import BaseModel

from newswatch.schemas import Source


class CollectorSettings(BaseModel):
    user_agent: str = "newswatch/0.1 (research project)"
    timeout_seconds: float = 15.0
    max_workers: int = 8
    lede_max_chars: int = 500
    # Look back this far on every run. Larger than the 4 h cadence on purpose: if a cron run is
    # skipped or late, the next one still catches the gap. Duplicates are harmless (idempotent).
    lookback_hours: int = 12
    # Dates further in the future than this are treated as broken feed dates.
    max_future_skew_hours: int = 1


class Settings(BaseModel):
    database_url: str | None = None
    log_level: str = "INFO"
    config_dir: Path = Path("config")
    migrations_dir: Path = Path("migrations")
    raw_dir: Path = Path("data/raw")
    collector: CollectorSettings = CollectorSettings()


def load_settings(config_dir: Path | None = None) -> Settings:
    """Read settings.yaml (if present), then let environment variables win."""
    config_dir = config_dir or Path(os.environ.get("NEWSWATCH_CONFIG_DIR", "config"))
    values: dict = {}
    settings_file = config_dir / "settings.yaml"
    if settings_file.exists():
        values = yaml.safe_load(settings_file.read_text(encoding="utf-8")) or {}
    values["config_dir"] = config_dir
    # Secrets and per-environment values come from env vars, never from the YAML files.
    if db_url := os.environ.get("DATABASE_URL"):
        values["database_url"] = db_url
    if log_level := os.environ.get("LOG_LEVEL"):
        values["log_level"] = log_level
    return Settings(**values)


def load_sources(path: Path) -> list[Source]:
    """Load the source registry and fail loudly on duplicate ids."""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    sources = [Source(**row) for row in data.get("sources", [])]
    ids = [s.source_id for s in sources]
    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        raise ValueError(f"duplicate source_id in {path}: {sorted(duplicates)}")
    return sources
