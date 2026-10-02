"""BGP analysis exceptions using the shared NetVoyager error structure."""

from uuid import UUID

from netvoyager_core.exceptions import NetVoyagerError


class InvalidBgpEvidenceError(NetVoyagerError):
    """Raised when evidence cannot satisfy the BGP conversion contract.

    Unknown origin alone is not an error. This exception reports malformed
    values, incompatible evidence kinds, or inconsistent origin attributes.
    """

    def __init__(self, *, evidence_id: UUID, reason: str) -> None:
        """Identify the rejected evidence and explain the contract violation."""
        self.evidence_id = evidence_id
        self.reason = reason

        super().__init__(
            code="analysis.invalid_bgp_evidence",
            message=f"Invalid BGP evidence {evidence_id}: {reason}",
            details={
                "evidence_id": str(evidence_id),
                "reason": reason,
            },
        )