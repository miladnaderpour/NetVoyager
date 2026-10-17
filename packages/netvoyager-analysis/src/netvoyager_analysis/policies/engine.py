
"""Load, register, and evaluate source trust policies.

The policy engine manages declarative source permissions for individual
domain claims and relationships.

It does not establish source facts, validate physical identities, or
modify canonical domain objects.
"""

from collections.abc import Mapping
from pathlib import Path
from typing import cast

import yaml

from .models import (
    ClaimActionPolicy,
    ClaimPolicy,
    PolicyEvaluationResult,
    SourceAuthority,
    SourceProfile,
    SourceTrustPolicy,
)
from .vocabulary import (
    CLAIM_ACTIONS,
    SUPPORTED_ACTIONS,
    SUPPORTED_CLAIMS,
    SUPPORTED_REQUIREMENTS,
)


class PolicyEngineError(ValueError):
    """Raised when a policy definition or registration is invalid."""


class _StrictPolicyLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate mapping keys."""


def _construct_mapping(
    loader: yaml.SafeLoader,
    node: yaml.MappingNode,
) -> dict[str, object]:
    """Build a mapping without accepting duplicate field names."""
    loader.flatten_mapping(node)
    keys: set[str] = set()

    for key_node, _ in node.value:
        key = loader.construct_object(key_node)

        if not isinstance(key, str):
            raise PolicyEngineError(
                "YAML mapping keys must be strings"
            )

        if key in keys:
            raise PolicyEngineError(
                f"Duplicate YAML field: {key}"
            )

        keys.add(key)

    return cast(
        dict[str, object],
        yaml.SafeLoader.construct_mapping(loader, node),
    )


_StrictPolicyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_mapping,
)


class PolicyEngine:
    """Manage source policies through one public interface.

    Policies are registered by source identity and collection method.

    Unknown sources, claims, actions, and unsatisfied requirements
    are denied during evaluation.

    Required condition results must come from trusted validators.
    The engine does not independently verify their truth.
    """

    def __init__(self) -> None:
        self._policies: dict[
            tuple[str, str],
            SourceTrustPolicy,
        ] = {}

    def register(
        self,
        policy: SourceTrustPolicy,
    ) -> None:
        """Validate and register a policy, rejecting duplicate profiles."""
        self._validate_policy(policy)

        key = (
            policy.profile.source_id,
            policy.profile.method,
        )

        if key in self._policies:
            raise PolicyEngineError(
                f"Source policy already registered: {key}"
            )

        self._policies[key] = policy

    def get(
        self,
        source_id: str,
        method: str,
    ) -> SourceTrustPolicy | None:
        """Return a registered policy or None when unavailable."""
        return self._policies.get((source_id, method))

    def load(
        self,
        path: Path,
    ) -> SourceTrustPolicy:
        """Load, validate, and register one YAML policy."""
        try:
            with path.open("r", encoding="utf-8") as stream:
                document = yaml.load(
                    stream,
                    Loader=_StrictPolicyLoader,
                )
        except (OSError, yaml.YAMLError) as exc:
            raise PolicyEngineError(
                f"Cannot load policy {path}: {exc}"
            ) from exc

        policy = self._parse_policy(document)
        self.register(policy)

        return policy

    def load_directory(
        self,
        path: Path,
    ) -> tuple[SourceTrustPolicy, ...]:
        """Load YAML policies from a directory in filename order.

        Validate the complete batch before changing the registry.
        Existing registrations remain unchanged if any file is invalid.
        """
        if not path.is_dir():
            raise PolicyEngineError(
                f"Policy directory does not exist: {path}"
            )

        files = sorted((
            *path.glob("*.yaml"),
            *path.glob("*.yml"),
        ))

        staged = PolicyEngine()

        for file in files:
            staged.load(file)

        for policy in staged.policies:
            self._validate_policy(policy)

            key = (
                policy.profile.source_id,
                policy.profile.method,
            )

            if key in self._policies:
                raise PolicyEngineError(
                    f"Source policy already registered: {key}"
                )

        for policy in staged.policies:
            self.register(policy)

        return staged.policies

    def evaluate(
        self,
        source_id: str,
        method: str,
        *,
        claim: str,
        action: str,
        requirements: Mapping[str, bool] | None = None,
    ) -> PolicyEvaluationResult:
        """Evaluate whether a source may perform an action.

        Only requirements belonging to the requested action are evaluated.

        Missing, unknown, and unsatisfied requirements deny permission.

        Requirement results must be supplied by a trusted validation
        component, not directly from unverified source observations.
        """
        policy = self.get(source_id, method)

        if policy is None:
            return self._result(
                source_id=source_id,
                method=method,
                version=0,
                claim=claim,
                action=action,
                authority="none",
                reason="Source policy is not registered",
            )

        claim_policy = policy.get_claim(claim)

        if claim_policy is None:
            return self._result(
                source_id=source_id,
                method=method,
                version=policy.version,
                claim=claim,
                action=action,
                authority="none",
                reason="Claim is not defined by the source policy",
            )

        reason: str | None = None
        failed: tuple[str, ...] = ()

        action_policy = claim_policy.get_action(action)

        if claim_policy.authority == "none":
            reason = "Source has no authority for this claim"

        elif action not in CLAIM_ACTIONS.get(claim, frozenset()):
            reason = "Action is not supported for this claim"

        elif action_policy is None:
            reason = "Action is not permitted by the source policy"

        else:
            supplied = requirements or {}

            failed = tuple(
                requirement
                for requirement in action_policy.requirements
                if (
                    requirement not in SUPPORTED_REQUIREMENTS
                    or supplied.get(requirement) is not True
                )
            )

            if failed:
                reason = "Required conditions are not satisfied"

        return self._result(
            source_id=source_id,
            method=method,
            version=policy.version,
            claim=claim,
            action=action,
            authority=claim_policy.authority,
            reason=reason,
            failed_requirements=failed,
        )

    def _validate_policy(
        self,
        policy: SourceTrustPolicy,
    ) -> None:
        """Reject unsupported claims, actions, and requirements."""
        for entry in policy.claims:
            if entry.claim not in SUPPORTED_CLAIMS:
                raise PolicyEngineError(
                    f"Unsupported claim: {entry.claim}"
                )

            for action_policy in entry.actions:
                action = action_policy.action

                if action not in SUPPORTED_ACTIONS:
                    raise PolicyEngineError(
                        f"Unsupported action: {action}"
                    )

                if action not in CLAIM_ACTIONS[entry.claim]:
                    raise PolicyEngineError(
                        f"Action {action} is invalid for {entry.claim}"
                    )

                for requirement in action_policy.requirements:
                    if requirement not in SUPPORTED_REQUIREMENTS:
                        raise PolicyEngineError(
                            f"Unsupported requirement: {requirement}"
                        )

    def _parse_policy(
        self,
        document: object,
    ) -> SourceTrustPolicy:
        """Construct typed policy models from validated YAML data."""
        root = self._mapping(
            document,
            "policy",
            {"source_id", "method", "description", "version", "claims"},
        )

        source_id = self._text(root.get("source_id"), "source_id")
        method = self._text(root.get("method"), "method")

        version = root.get("version")

        if type(version) is not int or version < 1:
            raise PolicyEngineError(
                "Policy version must be a positive integer"
            )

        description = root.get("description")

        if description is not None:
            description = self._text(
                description,
                "description",
            )

        entries = root.get("claims")

        if not isinstance(entries, list):
            raise PolicyEngineError(
                "claims must be a list"
            )

        claims: list[ClaimPolicy] = []

        for index, raw_entry in enumerate(entries):
            location = f"claims[{index}]"

            entry = self._mapping(
                raw_entry,
                location,
                {"claim", "authority", "actions"},
            )

            claim = self._text(
                entry.get("claim"),
                f"{location}.claim",
            )

            authority_value = self._text(
                entry.get("authority"),
                f"{location}.authority",
            )

            if authority_value not in {
                "none",
                "supporting",
                "trusted",
                "authoritative",
            }:
                raise PolicyEngineError(
                    f"Invalid authority: {authority_value}"
                )

            authority = cast(
                SourceAuthority,
                authority_value,
            )

            raw_actions = self._mapping(
                entry.get("actions", {}),
                f"{location}.actions",
                set(SUPPORTED_ACTIONS),
            )

            actions: list[ClaimActionPolicy] = []

            for action_name, raw_action in raw_actions.items():
                action_location = (
                    f"{location}.actions.{action_name}"
                )

                action_data = self._mapping(
                    raw_action,
                    action_location,
                    {"requirements"},
                )

                requirements = self._identifiers(
                    action_data.get("requirements", []),
                    f"{action_location}.requirements",
                )

                actions.append(
                    ClaimActionPolicy(
                        action=action_name,
                        requirements=requirements,
                    )
                )

            claims.append(
                ClaimPolicy(
                    claim=claim,
                    authority=authority,
                    actions=tuple(actions),
                )
            )

        try:
            return SourceTrustPolicy(
                profile=SourceProfile(
                    source_id=source_id,
                    method=method,
                    description=description,
                ),
                version=version,
                claims=tuple(claims),
            )
        except ValueError as exc:
            raise PolicyEngineError(str(exc)) from exc

    @staticmethod
    def _mapping(
        value: object,
        location: str,
        allowed_fields: set[str],
    ) -> dict[str, object]:
        """Require a mapping with only supported fields."""
        if not isinstance(value, dict):
            raise PolicyEngineError(
                f"{location} must be a mapping"
            )

        if any(not isinstance(key, str) for key in value):
            raise PolicyEngineError(
                f"{location} contains non-string keys"
            )

        unknown = value.keys() - allowed_fields

        if unknown:
            raise PolicyEngineError(
                f"{location} has unknown fields: {sorted(unknown)}"
            )

        return value

    @staticmethod
    def _text(
        value: object,
        location: str,
    ) -> str:
        """Require a nonempty string."""
        if not isinstance(value, str) or not value.strip():
            raise PolicyEngineError(
                f"{location} must be a nonempty string"
            )

        return value.strip()

    @classmethod
    def _identifiers(
        cls,
        value: object,
        location: str,
    ) -> tuple[str, ...]:
        """Require a list of unique nonempty strings."""
        if not isinstance(value, list):
            raise PolicyEngineError(
                f"{location} must be a list"
            )

        items = tuple(
            cls._text(item, location)
            for item in value
        )

        if len(items) != len(set(items)):
            raise PolicyEngineError(
                f"{location} contains duplicate values"
            )

        return items

    @staticmethod
    def _result(
        *,
        source_id: str,
        method: str,
        version: int,
        claim: str,
        action: str,
        authority: SourceAuthority,
        reason: str | None,
        failed_requirements: tuple[str, ...] = (),
    ) -> PolicyEvaluationResult:
        """Construct a policy evaluation result."""
        return PolicyEvaluationResult(
            source_id=source_id,
            method=method,
            policy_version=version,
            claim=claim,
            action=action,
            status="allowed" if reason is None else "denied",
            authority=authority,
            reason=reason,
            failed_requirements=failed_requirements,
        )

    @property
    def policies(self) -> tuple[SourceTrustPolicy, ...]:
        """Return registered policies in insertion order."""
        return tuple(self._policies.values())
