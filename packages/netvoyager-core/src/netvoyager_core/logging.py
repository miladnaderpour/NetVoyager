"""Application logging with structured fields and conservative redaction.

Call setup_logging once at the API, worker, or scheduler entry point. Never log
secrets or raw network output in the message string: only structured extra
fields can be redacted reliably.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .config import LoggingSettings
from .exceptions import NetVoyagerConfigError
from .models import LogTarget

SENSITIVE_KEYS = ("password", "secret", "token", "authorization", "cookie", "api_key", "credential")
STANDARD_KEYS = frozenset(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}


def _redact(value: Any, key: str = "") -> Any:
    if any(sensitive in key.lower() for sensitive in SENSITIVE_KEYS):
        return "***REDACTED***"
    if isinstance(value, dict):
        return {str(k): _redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact(item) for item in value]
    return value


def _extras(record: logging.LogRecord) -> dict[str, Any]:
    return {
        key: _redact(value, key)
        for key, value in record.__dict__.items()
        if not key.startswith("_") and key not in STANDARD_KEYS
    }


def _timestamp(record: logging.LogRecord) -> str:
    return datetime.fromtimestamp(record.created, UTC).isoformat()


class JsonLogFormatter(logging.Formatter):
    def __init__(self, service: str = "netvoyager") -> None:
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            **_extras(record),
            "timestamp": _timestamp(record),
            "service": self.service,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        return json.dumps(payload, sort_keys=True, default=str)


class TextLogFormatter(logging.Formatter):
    def __init__(self, service: str = "netvoyager") -> None:
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        line = f"{_timestamp(record)} {self.service} {record.levelname} {record.name} {record.getMessage()}"
        extras = _extras(record)
        if extras:
            line += " " + json.dumps(extras, sort_keys=True, default=str)
        return line


def parse_log_targets(value: str) -> list[LogTarget]:
    """Parse validated logging targets without echoing configuration secrets."""

    try:
        raw = json.loads(value)
        if not isinstance(raw, list) or not raw:
            raise ValueError("Expected a nonempty list")
        targets = [LogTarget.model_validate(target) for target in raw]
        if len({target.name for target in targets}) != len(targets):
            raise ValueError("Duplicate target name")
        return targets
    except (ValueError, TypeError, ValidationError) as exc:
        raise NetVoyagerConfigError(
            code="config.invalid_log_targets",
            message="NETVOYAGER_LOG_TARGETS_JSON must contain valid, uniquely named targets.",
        ) from exc


def _build_handler(target: LogTarget, service: str) -> logging.Handler:
    if target.output == "file":
        if target.file_path is None:
            raise NetVoyagerConfigError(
                code="config.missing_log_file_path",
                message="A file logging target requires file_path.",
            )
        path = Path(target.file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        handler: logging.Handler = logging.FileHandler(path, encoding="utf-8")
    else:
        handler = logging.StreamHandler(sys.stdout)

    handler.setLevel(target.level)
    handler.setFormatter(JsonLogFormatter(service) if target.format == "json" else TextLogFormatter(service))
    return handler


def setup_logging(settings: LoggingSettings | None = None, *, service: str = "netvoyager") -> None:
    """Configure only the NetVoyager logger; do not replace root handlers."""

    settings = settings or LoggingSettings.from_env()
    try:
        targets = (
            parse_log_targets(settings.targets_json)
            if settings.targets_json
            else [LogTarget(name="default", output=settings.output, level=settings.level,
                            format=settings.format, file_path=settings.file_path)]
        )
    except ValidationError as exc:
        raise NetVoyagerConfigError(
            code="config.invalid_log_settings", message="Invalid NetVoyager logging settings."
        ) from exc

    handlers: list[logging.Handler] = []
    try:
        for target in targets:
            handlers.append(_build_handler(target, service))
    except Exception:
        for handler in handlers:
            handler.close()
        raise

    logger = logging.getLogger("netvoyager")
    for old_handler in logger.handlers[:]:
        logger.removeHandler(old_handler)
        old_handler.close()
    for handler in handlers:
        logger.addHandler(handler)
    logger.setLevel(min(handler.level for handler in handlers))
    logger.propagate = False


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a logger in the NetVoyager namespace."""

    if name is None or name == "netvoyager":
        return logging.getLogger("netvoyager")
    if name.startswith("netvoyager."):
        return logging.getLogger(name)
    return logging.getLogger(f"netvoyager.{name}")
