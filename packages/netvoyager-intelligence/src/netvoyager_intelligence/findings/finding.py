
"""SQLAlchemy model for findings derived from network analysis.

Findings describe noteworthy conditions identified during discovery,
validation, and reconciliation.

The intelligence package owns finding records, while evaluation and
decision-making remain the responsibility of analysis services.
"""

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Index, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from netvoyager_intelligence.base import IntelligenceBase
from netvoyager_intelligence.evidence.record import JsonValue


FindingSeverity = Literal[
    "info",
    "warning",
    "error",
]


class Finding(IntelligenceBase):
    """Represent a noteworthy condition produced by analysis.

    A finding has an independent UUID and describes the observed
    condition through its kind, severity, message, and optional details.

    Object references use a UUID and an optional object type.
    Findings without a specific domain object are also supported.

    Details contain JSON-compatible values and are retained for
    inspection rather than domain identity matching.

    Findings do not perform validation, reconciliation, or
    automatic lifecycle transitions.
    """

    __tablename__ = "findings"

    __table_args__ = (
        Index(
            "ix_findings_object_id",
            "object_id",
        ),
        Index(
            "ix_findings_kind",
            "kind",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
    )

    kind: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    severity: Mapped[FindingSeverity] = mapped_column(
        String(20),
        nullable=False,
    )

    message: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    object_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    object_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )

    details: Mapped[dict[str, JsonValue]] = mapped_column(
        JSON,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    def __init__(
        self,
        kind: str,
        severity: FindingSeverity,
        message: str,
        object_type: str | None = None,
        object_id: UUID | None = None,
        details: dict[str, JsonValue] | None = None,
        *,
        id: UUID | None = None,
        created_at: datetime | None = None,
    ) -> None:
        """Initialize a finding with its identity and timestamp."""
        self.kind = kind
        self.severity = severity
        self.message = message
        self.object_type = object_type
        self.object_id = object_id
        self.details = details if details is not None else {}
        self.id = id if id is not None else uuid4()
        self.created_at = (
            created_at
            if created_at is not None
            else datetime.now(timezone.utc)
        )
