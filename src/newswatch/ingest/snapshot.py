"""Daily JSONL snapshot: a plain-file backup and the raw material for replay evaluation."""

import json
import logging
from datetime import date
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


def write_snapshot(rows: list[dict[str, Any]], day: date, raw_dir: Path) -> Path:
    """Write one JSON object per line to data/raw/YYYY-MM-DD.jsonl (overwrites: safe to re-run)."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / f"{day.isoformat()}.jsonl"
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, default=str, ensure_ascii=False) + "\n")
    log.info("snapshot written", extra={"path": str(path), "rows": len(rows)})
    return path
