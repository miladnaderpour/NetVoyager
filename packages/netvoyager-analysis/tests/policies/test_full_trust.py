
"""Tests for administrator-defined full source trust."""

from pathlib import Path

import pytest

from netvoyager_analysis.policies.engine import (
    PolicyEngine,
    PolicyEngineError,
)


PROJECT_ROOT = Path(__file__).resolve().parents[4]
POLICY_DIRECTORY = PROJECT_ROOT / "examples" / "policies"


@pytest.fixture
def engine() -> PolicyEngine:
    """Load the configured example source policies."""
    result = PolicyEngine()
    result.load_directory(POLICY_DIRECTORY)
    return result


def test_meraki_policy_is_fully_trusted(
    engine: PolicyEngine,
) -> None:
    policy = engine.get("meraki", "api")

    assert policy is not None
    assert policy.fully_trusted is True
    assert policy.claims == ()


@pytest.mark.parametrize(
    ("claim", "action"),
    [
        ("device.physical_identity", "record_observation"),
        ("device.physical_identity", "create_candidate"),
        ("device.physical_identity", "create_canonical_device"),
        ("device.physical_identity", "promote_candidate"),
        ("prefix.existence", "record_observation"),
        ("prefix.existence", "create_candidate"),
        ("prefix.existence", "correlate_candidate"),
        ("prefix.existence", "create_canonical_prefix"),
        ("prefix.existence", "promote_candidate"),
        ("device.management_ip", "confirm_attribute"),
        ("relationship.prefix_site", "validate_relationship"),
    ],
)
def test_full_trust_authorizes_supported_actions(
    engine: PolicyEngine,
    claim: str,
    action: str,
) -> None:
    result = engine.evaluate(
        "meraki",
        "api",
        claim=claim,
        action=action,
    )

    assert result.allowed
    assert result.authority == "authoritative"
    assert result.failed_requirements == ()
    assert result.policy_version == 1


def test_full_trust_ignores_failed_evidence_requirements(
    engine: PolicyEngine,
) -> None:
    result = engine.evaluate(
        "meraki",
        "api",
        claim="device.physical_identity",
        action="create_canonical_device",
        requirements={
            "unique_physical_serial": False,
            "unambiguous_device_match": False,
        },
    )

    assert result.allowed
    assert result.authority == "authoritative"


def test_full_trust_rejects_unsupported_claim_action(
    engine: PolicyEngine,
) -> None:
    result = engine.evaluate(
        "meraki",
        "api",
        claim="device.host_name",
        action="create_canonical_prefix",
    )

    assert not result.allowed


def test_full_trust_rejects_unknown_claim(
    engine: PolicyEngine,
) -> None:
    result = engine.evaluate(
        "meraki",
        "api",
        claim="unknown.claim",
        action="record_observation",
    )

    assert not result.allowed


def test_unknown_source_remains_denied(
    engine: PolicyEngine,
) -> None:
    result = engine.evaluate(
        "unknown",
        "api",
        claim="prefix.existence",
        action="create_canonical_prefix",
    )

    assert not result.allowed


def test_full_trust_does_not_apply_to_another_method(
    engine: PolicyEngine,
) -> None:
    result = engine.evaluate(
        "meraki",
        "ssh",
        claim="prefix.existence",
        action="create_canonical_prefix",
    )

    assert not result.allowed


def test_conditional_source_still_requires_validation(
    engine: PolicyEngine,
) -> None:
    result = engine.evaluate(
        "paloalto",
        "local_rib",
        claim="prefix.existence",
        action="create_canonical_prefix",
    )

    assert not result.allowed
    assert result.failed_requirements == (
        "valid_network_prefix",
        "verified_reporting_source",
    )


def test_conditional_source_can_promote_valid_prefix(
    engine: PolicyEngine,
) -> None:
    result = engine.evaluate(
        "paloalto",
        "local_rib",
        claim="prefix.existence",
        action="promote_candidate",
        requirements={
            "valid_network_prefix": True,
            "verified_reporting_source": True,
        },
    )

    assert result.allowed
    assert result.policy_version == 2


def test_excel_cannot_create_canonical_device(
    engine: PolicyEngine,
) -> None:
    result = engine.evaluate(
        "excel_inventory",
        "device_inventory",
        claim="device.physical_identity",
        action="create_canonical_device",
    )

    assert not result.allowed


def test_full_trust_requires_boolean(tmp_path: Path) -> None:
    path = tmp_path / "invalid.yaml"
    path.write_text(
        """
source_id: test_source
method: api
version: 1
fully_trusted: "yes"
claims: []
""",
        encoding="utf-8",
    )

    with pytest.raises(
        PolicyEngineError,
        match="fully_trusted must be a boolean",
    ):
        PolicyEngine().load(path)


def test_ordinary_source_defaults_to_not_fully_trusted(
    engine: PolicyEngine,
) -> None:
    policy = engine.get(
        "excel_inventory",
        "device_inventory",
    )

    assert policy is not None
    assert policy.fully_trusted is False
