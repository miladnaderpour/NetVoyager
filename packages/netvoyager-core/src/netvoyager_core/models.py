"""Models shared by core infrastructure."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class LogTarget(BaseModel):
    """Validated destination for one application logging handler."""

    name: str
    output: Literal["stdout", "file"] = "stdout"
    level: str = "INFO"
    format: Literal["json", "text"] = "json"
    file_path: str | None = None

    @field_validator("level")
    @classmethod
    def valid_level(cls, value: str) -> str:
        import logging

        level = value.upper()
        if level not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            raise ValueError("Unsupported logging level")
        return level

    @field_validator("file_path")
    @classmethod
    def non_empty_file_path(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("file_path must not be blank")
        return value
