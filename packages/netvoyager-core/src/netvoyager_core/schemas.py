"""Stable result envelopes for server-side service and API boundaries."""

from datetime import UTC, datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ServiceError(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ServiceMeta(BaseModel):
    service: str
    version: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    request_id: str | None = None
    duration_seconds: float | None = None


class ServiceResult(BaseModel, Generic[T]):
    ok: bool
    code: str
    data: T | None = None
    error: ServiceError | None = None
    meta: ServiceMeta
