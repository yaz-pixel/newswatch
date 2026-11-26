"""JSON logs to stdout, with a run_id on every line (12-factor: the platform keeps the logs)."""

import json
import logging
import sys
import uuid
from datetime import UTC, datetime

# Attributes every LogRecord has; anything else was passed through `extra=` and is a custom field.
_STANDARD_ATTRS = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {
    "message",
    "asctime",
}


class JsonFormatter(logging.Formatter):
    def __init__(self, run_id: str) -> None:
        super().__init__()
        self.run_id = run_id

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "run_id": self.run_id,
        }
        payload.update({k: v for k, v in record.__dict__.items() if k not in _STANDARD_ATTRS})
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def setup_logging(level: str = "INFO") -> str:
    """Configure the root logger once and return the run_id used on every line."""
    run_id = uuid.uuid4().hex[:12]
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter(run_id))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())
    logging.getLogger("httpx").setLevel(logging.WARNING)
    return run_id
