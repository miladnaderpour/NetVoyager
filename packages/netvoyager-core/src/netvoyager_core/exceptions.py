"""Shared application errors independent of HTTP and CLI presentation."""

from typing import Any


class NetVoyagerError(Exception):
    """An error with a stable code and safe, structured details."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "details": self.details}


class NetVoyagerConfigError(NetVoyagerError):
    """Invalid application configuration."""


class NetVoyagerInvariantError(NetVoyagerError):
    """An operation would violate a domain rule."""
