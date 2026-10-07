"""Models for analysis findings."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4


FindingSeverity = Literal[
    "info",
    "warning",
    "error",
]


@dataclass(frozen=True, slots=True)
class Finding:
    """A derived issue or noteworthy condition found during analysis."""

    kind: str
    severity: FindingSeverity
    message: str

    object_type: str | None = None
    object_id: UUID | str | None = None
    details: dict[str, object] = field(default_factory=dict)

    id: UUID = field(
        default_factory=uuid4,
        kw_only=True,
    )
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
        kw_only=True,
    )