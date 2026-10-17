
"""Tests for source policy loading and evaluation."""

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
    """Return an engine loaded with example source policies."""
    policy_engine = PolicyEngine()
    policy_engine.load_directory(POLICY_DIRECTORY)
    return policy_engine


def test_load_example_policies(engine: PolicyEngine) -> None:
    """Load all three example policies."""
    assert len(engine.policies) == 3

    assert engine.get("excel_inventory", "device_inventory")
    assert engine.get("paloalto", "local_rib")
    assert engine.get(
        "paloalto_panorama",
        "managed_device_inventory",
    )


def test_excel_cannot_create_canonical_device(
    engine: PolicyEngine,
) -> None:
    """Excel inventory cannot establish canonical physical identity."""
    result = engine.evaluate(
        "excel_inventory",
        "device_inventory",
        claim="device.physical_identity",
        action="create_canonical_device",
    )

    assert not result.allowed


def test_excel_can_create_device_candidate(
    engine: PolicyEngine,
) -> None:
    """Excel inventory can create provisional physical-device candidates."""
    result = engine.evaluate(
        "excel_inventory",
        "device_inventory",
        claim="device.physical_identity",
        action="create_candidate",
    )

    assert result.allowed


def test_bgp_can_create_canonical_prefix(
    engine: PolicyEngine,
) -> None:
    """Valid RIB observations can establish canonical IPAM prefixes."""
    result = engine.evaluate(
        "paloalto",
        "local_rib",
        claim="prefix.existence",
        action="create_canonical_prefix",
        requirements={
            "valid_network_prefix": True,
            "verified_reporting_source": True,
        },
    )

    assert result.allowed


def test_bgp_denies_missing_requirements(
    engine: PolicyEngine,
) -> None:
    """Prefix promotion requires all configured conditions."""
    result = engine.evaluate(
        "paloalto",
        "local_rib",
        claim="prefix.existence",
        action="create_canonical_prefix",
        requirements={
            "valid_network_prefix": True,
        },
    )

    assert not result.allowed
    assert result.failed_requirements == (
        "verified_reporting_source",
    )


def test_panorama_can_create_canonical_device(
    engine: PolicyEngine,
) -> None:
    """Trusted per-chassis identity can authorize device creation."""
    result = engine.evaluate(
        "paloalto_panorama",
        "managed_device_inventory",
        claim="device.physical_identity",
        action="create_canonical_device",
        requirements={
            "unique_physical_serial": True,
            "unambiguous_device_match": True,
        },
    )

    assert result.allowed


def test_panorama_denies_ambiguous_identity(
    engine: PolicyEngine,
) -> None:
    """Ambiguous physical identity cannot authorize promotion."""
    result = engine.evaluate(
        "paloalto_panorama",
        "managed_device_inventory",
        claim="device.physical_identity",
        action="promote_candidate",
        requirements={
            "unique_physical_serial": True,
            "unambiguous_device_match": False,
        },
    )

    assert not result.allowed


def test_unknown_source_denied(engine: PolicyEngine) -> None:
    """Unregistered sources have no policy permissions."""
    result = engine.evaluate(
        "unknown_source",
        "unknown_method",
        claim="device.physical_identity",
        action="create_canonical_device",
    )

    assert not result.allowed


def test_invalid_claim_action_denied(
    engine: PolicyEngine,
) -> None:
    """Device attributes cannot authorize prefix creation."""
    result = engine.evaluate(
        "excel_inventory",
        "device_inventory",
        claim="device.host_name",
        action="create_canonical_prefix",
    )

    assert not result.allowed


def test_duplicate_policy_registration(
    engine: PolicyEngine,
) -> None:
    """The same source and collection method cannot register twice."""
    policy = engine.get(
        "excel_inventory",
        "device_inventory",
    )

    assert policy is not None

    with pytest.raises(PolicyEngineError):
        engine.register(policy)


def test_panorama_records_ambiguous_identity(
    engine: PolicyEngine,
) -> None:
    """Observation recording does not require identity confirmation."""
    result = engine.evaluate(
        "paloalto_panorama",
        "managed_device_inventory",
        claim="device.physical_identity",
        action="record_observation",
    )

    assert result.allowed
    assert result.failed_requirements == ()


def test_panorama_creates_ambiguous_candidate(
    engine: PolicyEngine,
) -> None:
    """Candidate creation is allowed without a unique serial."""
    result = engine.evaluate(
        "paloalto_panorama",
        "managed_device_inventory",
        claim="device.physical_identity",
        action="create_candidate",
    )

    assert result.allowed


def test_panorama_denies_promotion_without_identity(
    engine: PolicyEngine,
) -> None:
    """Promotion requires strong, unambiguous physical identity."""
    result = engine.evaluate(
        "paloalto_panorama",
        "managed_device_inventory",
        claim="device.physical_identity",
        action="promote_candidate",
    )

    assert not result.allowed
    assert result.failed_requirements == (
        "unique_physical_serial",
        "unambiguous_device_match",
    )


def test_bgp_records_route_without_validation(
    engine: PolicyEngine,
) -> None:
    """Route evidence may be recorded before prefix validation."""
    result = engine.evaluate(
        "paloalto",
        "local_rib",
        claim="prefix.existence",
        action="record_observation",
    )

    assert result.allowed


def test_panorama_attribute_has_independent_requirements(
    engine: PolicyEngine,
) -> None:
    """Management IP confirmation requires management-specific evidence."""
    result = engine.evaluate(
        "paloalto_panorama",
        "managed_device_inventory",
        claim="device.management_ip",
        action="confirm_attribute",
        requirements={
            "verified_device_identity": True,
            "verified_management_address": False,
        },
    )

    assert not result.allowed
    assert result.failed_requirements == (
        "verified_management_address",
    )


def test_reject_old_claim_level_requirements(
    tmp_path: Path,
) -> None:
    """Reject the obsolete claim-level requirements schema."""
    policy_file = tmp_path / "invalid.yaml"

    policy_file.write_text(
        """
source_id: test_source
method: test_method
version: 1
claims:
  - claim: prefix.existence
    authority: trusted
    actions:
      record_observation: {}
    requirements:
      - valid_network_prefix
""",
        encoding="utf-8",
    )

    engine = PolicyEngine()

    with pytest.raises(
        PolicyEngineError,
        match="unknown fields",
    ):
        engine.load(policy_file)
