
"""Tests for provisional device candidate attribute enrichment.

All device identifiers, sites, addresses and source values are synthetic.
"""

from ipaddress import IPv4Address

import pytest

from netvoyager_analysis.devices.candidate_enrichment import (
    FINDING_KIND,
    enrich_device_candidate,
)
from netvoyager_analysis.devices.matching_rules import SourceRef
from netvoyager_analysis.devices.observations import DeviceObservation
from netvoyager_network.device.discovery.models import (
    DeviceDiscoveryCandidate,
)


SOURCE = SourceRef(
    source_id="test_inventory",
    method="device_inventory",
)


def make_candidate(**overrides):
    """Build a provisional candidate with synthetic identifiers."""
    values = {
        "name": "SW-LAB-01",
        "serial_number": "TEST-SERIAL-001",
    }
    values.update(overrides)
    return DeviceDiscoveryCandidate(**values)


def make_observation(**overrides):
    """Build an independent source observation."""
    values = {
        "local_ref": "test:row:2",
        "inventory_name": "SW-LAB-01",
        "serial_number": "TEST-SERIAL-001",
    }
    values.update(overrides)
    return DeviceObservation(**values)


def test_fills_missing_inventory_attributes():
    candidate = make_candidate()

    observation = make_observation(
        site="LAB-A",
        role="access_switch",
        primary_ipv4="192.0.2.11",
        manufacturer="Example Vendor",
        model="Example Switch",
        software_version="1.0",
        asset_tag="TEST-ASSET-001",
    )

    result = enrich_device_candidate(
        candidate,
        observation,
        source=SOURCE,
    )

    assert result.candidate.site == "LAB-A"
    assert result.candidate.role == "access_switch"
    assert result.candidate.primary_ipv4 == IPv4Address(
        "192.0.2.11"
    )
    assert result.candidate.manufacturer == "Example Vendor"
    assert result.candidate.model == "Example Switch"
    assert result.candidate.software_version == "1.0"
    assert result.candidate.asset_tag == "TEST-ASSET-001"

    assert len(result.changed_fields) == 7
    assert result.findings == ()

    assert result.candidate.candidate_id == candidate.candidate_id
    assert candidate.site is None


def test_identical_values_do_not_change_candidate():
    candidate = make_candidate(
        site="LAB-A",
        manufacturer="Example Vendor",
    )

    observation = make_observation(
        site="lab-a",
        manufacturer="example vendor",
    )

    result = enrich_device_candidate(
        candidate,
        observation,
        source=SOURCE,
    )

    assert result.candidate is candidate
    assert result.changed_fields == ()
    assert result.findings == ()


def test_conflicting_value_creates_finding():
    candidate = make_candidate(
        site="LAB-A",
        model="Example Switch A",
    )

    observation = make_observation(
        site="LAB-B",
        model="Example Switch B",
    )

    result = enrich_device_candidate(
        candidate,
        observation,
        source=SOURCE,
    )

    assert result.candidate is candidate
    assert result.changed_fields == ()
    assert len(result.findings) == 2

    by_attribute = {
        finding.details["attribute"]: finding
        for finding in result.findings
    }

    site_finding = by_attribute["site"]

    assert site_finding.kind == FINDING_KIND
    assert site_finding.severity == "warning"
    assert site_finding.object_type == (
        "device_discovery_candidate"
    )
    assert site_finding.object_id == candidate.candidate_id
    assert site_finding.details["existing_value"] == "LAB-A"
    assert site_finding.details["incoming_value"] == "LAB-B"
    assert site_finding.details["source_id"] == SOURCE.source_id
    assert site_finding.details["source_method"] == SOURCE.method
    assert site_finding.details["observation_id"] == str(
        observation.observation_id
    )

    assert by_attribute["model"].details["existing_value"] == (
        "Example Switch A"
    )
    assert by_attribute["model"].details["incoming_value"] == (
        "Example Switch B"
    )


def test_missing_incoming_values_do_not_erase_attributes():
    candidate = make_candidate(
        site="LAB-A",
        role="access_switch",
        model="Example Switch",
    )

    observation = make_observation()

    result = enrich_device_candidate(
        candidate,
        observation,
        source=SOURCE,
    )

    assert result.candidate is candidate
    assert result.changed_fields == ()
    assert result.findings == ()


def test_can_fill_missing_and_report_conflict_together():
    candidate = make_candidate(
        site="LAB-A",
        role=None,
    )

    observation = make_observation(
        site="LAB-B",
        role="distribution_switch",
    )

    result = enrich_device_candidate(
        candidate,
        observation,
        source=SOURCE,
    )

    assert result.candidate.site == "LAB-A"
    assert result.candidate.role == "distribution_switch"
    assert result.changed_fields == ("role",)

    assert len(result.findings) == 1
    assert result.findings[0].details["attribute"] == "site"


def test_invalid_ipv4_is_rejected():
    candidate = make_candidate()

    observation = make_observation(
        primary_ipv4="not-an-ip-address",
    )

    with pytest.raises(ValueError):
        enrich_device_candidate(
            candidate,
            observation,
            source=SOURCE,
        )


@pytest.mark.parametrize("status", ["rejected", "retired"])
def test_inactive_candidate_cannot_be_enriched(status):
    candidate = make_candidate(status=status)
    observation = make_observation(site="LAB-A")

    with pytest.raises(ValueError):
        enrich_device_candidate(
            candidate,
            observation,
            source=SOURCE,
        )


def test_repeated_enrichment_does_not_change_identity():
    candidate = make_candidate()
    observation = make_observation(site="LAB-A")

    first = enrich_device_candidate(
        candidate,
        observation,
        source=SOURCE,
    )

    second = enrich_device_candidate(
        first.candidate,
        observation,
        source=SOURCE,
    )

    assert first.candidate.candidate_id == candidate.candidate_id
    assert second.candidate.candidate_id == candidate.candidate_id
    assert second.candidate == first.candidate
    assert second.changed_fields == ()
    assert second.findings == ()
