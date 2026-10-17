
"""Models for source profiles and claim-specific trust policies.

Source policies describe which claims a collection method may establish
and which actions are permitted for those claims.

Policy evaluation, evidence validation, and reconciliation decisions
are managed separately by the analysis layer.
"""

from dataclasses import dataclass
from typing import Literal, TypeAlias


SourceAuthority: TypeAlias = Literal[
    "none",
    "supporting",
    "trusted",
    "authoritative",
]


@dataclass(frozen=True, slots=True)
class SourceProfile:
    """Identify the origin and collection method of source observations.

    A profile identifies how evidence was collected, independently of
    the claims that the source is authorized to establish.

    Trust permissions are defined in SourceTrustPolicy.
    """

    source_id: str
    method: str
    description: str | None = None

    def __post_init__(self) -> None:
        """Validate source identity and collection method."""
        if not self.source_id.strip():
            raise ValueError("Source ID cannot be empty")

        if not self.method.strip():
            raise ValueError("Collection method cannot be empty")


@dataclass(frozen=True, slots=True)
class ClaimActionPolicy:
    """Define one permitted action and its required conditions.

    Requirements are evaluated independently for each action.
    An action without requirements may be authorized directly.
    """

    action: str
    requirements: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Validate action and requirement identifiers."""
        if not self.action.strip():
            raise ValueError("Policy action cannot be empty")

        if any(
            not requirement.strip()
            for requirement in self.requirements
        ):
            raise ValueError("Policy requirements cannot be empty")

        if len(self.requirements) != len(set(self.requirements)):
            raise ValueError(
                "Duplicate policy requirements are not allowed"
            )


@dataclass(frozen=True, slots=True)
class ClaimPolicy:
    """Define authority and permitted actions for one semantic claim.

    Each action has its own requirements. Claim authority remains
    independent of individual action permissions.

    Policy evaluation and reconciliation are managed separately.
    """

    claim: str
    authority: SourceAuthority
    actions: tuple[ClaimActionPolicy, ...] = ()

    def __post_init__(self) -> None:
        """Validate claim identity, authority, and action uniqueness."""
        if not self.claim.strip():
            raise ValueError("Claim name cannot be empty")

        if self.authority not in {
            "none",
            "supporting",
            "trusted",
            "authoritative",
        }:
            raise ValueError(
                f"Invalid source authority: {self.authority}"
            )

        action_names = tuple(
            action.action
            for action in self.actions
        )

        if len(action_names) != len(set(action_names)):
            raise ValueError(
                "Duplicate policy actions are not allowed"
            )

        if self.authority == "none" and self.actions:
            raise ValueError(
                "A claim with no authority cannot permit actions"
            )

    def get_action(
        self,
        action: str,
    ) -> ClaimActionPolicy | None:
        """Return the policy for an action, or None if unavailable."""
        for action_policy in self.actions:
            if action_policy.action == action:
                return action_policy

        return None



@dataclass(frozen=True, slots=True)
class SourceTrustPolicy:
    """Define claim-level permissions for a source collection method.

    Each policy belongs to one source profile and contains independently
    defined permissions for domain attributes and relationships.

    Policy versions allow reconciliation decisions to reference the
    rules applied when those decisions were made.

    Unspecified claims have no permissions by default.
    """

    profile: SourceProfile
    version: int
    claims: tuple[ClaimPolicy, ...] = ()

    def __post_init__(self) -> None:
        """Validate policy version and claim uniqueness."""
        if self.version < 1:
            raise ValueError("Policy version must be positive")

        claim_names = [policy.claim for policy in self.claims]

        if len(claim_names) != len(set(claim_names)):
            raise ValueError(
                "Duplicate claim definitions are not allowed"
            )

    def get_claim(self, claim: str) -> ClaimPolicy | None:
        """Return the policy for a claim, or None when undefined."""
        for policy in self.claims:
            if policy.claim == claim:
                return policy

        return None

@dataclass(frozen=True, slots=True)
class PolicyEvaluationResult:
    """Result of evaluating a source policy action."""

    source_id: str
    method: str
    policy_version: int
    claim: str
    action: str
    status: Literal["allowed", "denied"]
    authority: SourceAuthority
    reason: str | None = None
    failed_requirements: tuple[str, ...] = ()

    @property
    def allowed(self) -> bool:
        """Return whether the action was authorized."""
        return self.status == "allowed"

