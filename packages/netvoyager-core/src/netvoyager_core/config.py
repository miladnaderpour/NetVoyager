"""Shared logging configuration; each app owns its other settings."""

import os

from pydantic import BaseModel


class LoggingSettings(BaseModel):
    level: str = "INFO"
    format: str = "json"
    output: str = "stdout"
    file_path: str | None = None
    targets_json: str | None = None

    @classmethod
    def from_env(cls) -> "LoggingSettings":
        """Read only logging variables; firewall and DB settings belong to apps."""

        return cls(
            level=os.getenv("NETVOYAGER_LOG_LEVEL", "INFO"),
            format=os.getenv("NETVOYAGER_LOG_FORMAT", "json"),
            output=os.getenv("NETVOYAGER_LOG_OUTPUT", "stdout"),
            file_path=os.getenv("NETVOYAGER_LOG_FILE_PATH"),
            targets_json=os.getenv("NETVOYAGER_LOG_TARGETS_JSON"),
        )
