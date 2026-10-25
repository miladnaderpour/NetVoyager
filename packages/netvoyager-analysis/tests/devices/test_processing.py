
"""Tests for the Device Analysis processing entry point.

All data is synthetic. No customer inventory, serials, hostnames,
or infrastructure addresses are used.

The repository doubles intentionally expose only operations required
by the current Device Processing implementation.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from netvoyager_core.exceptions import NetVoyagerConfigError

from netvoyager_analysis.devices.observations import (
    DeviceObservation,
)
from netvoyager_analysis.devices.processing import process
from netvoyager_analysis.sources.models import (
    Source,
    SourceDataset,
)
from netvoyager_network.device.discovery.models import (
    DeviceDiscoveryCandidate,
)
from netvoyager_network.device.models import NetworkDevice


class _Permission:
    """Simple permission result for policy tests."""

    allowed = True


class _Policies:
    """Permit candidate creation for the synthetic source."""

    def evaluate(
        self,
        source_id,
        method,
        *,
        claim,
        action,
    ):
        assert source_id == "test_inventory"
        assert method == "device_inventory"
        assert claim == "device.physical_identity"
        assert action == "create_candidate"
        return _Permission()


class _DeniedPolicies:
    """Reject candidate creation."""

    def evaluate(self, *args, **kwargs):
        class Permission:
            allowed = False

        return Permission()


class _DiscoveryRepository:
    """In-memory discovery repository for processor tests."""

    def __init__(self):
        self.candidates = {}

    def get_candidate(self, candidate_id):
        return self.candidates.get(candidate_id)

    def find_by_serial(self, serial_number):
        return tuple(
            candidate
            for candidate in self.candidates.values()
            if candidate.serial_number == serial_number
        )

    def find_by_serial_suffix(self, suffix):
        return tuple(
            candidate
            for candidate in self.candidates.values()
            if candidate.serial_number
            and candidate.serial_number.endswith(suffix)
        )

    def add_candidate(self, candidate):
        self.candidates[candidate.candidate_id] = candidate

    def save_candidate(self, candidate):
        self.candidates[candidate.candidate_id] = candidate


class _CanonicalRepository:
    """In-memory canonical lookup repository."""

    def __init__(self):
        self.devices = {}

    def find_by_serial(self, serial_number):
        return tuple(
            device
            for device in self.devices.values()
            if device.serial_number == serial_number
        )

    def find_by_serial_suffix(self, suffix):
        return tuple(
            device
            for device in self.devices.values()
            if device.serial_number
            and device.serial_number.endswith(suffix)
        )


class _FindingsRepository:
    """In-memory Finding repository."""

    def __init__(self):
        self.records = []

    def for_object(
        self,
        object_id,
        *,
        object_type=None,
    ):
        return tuple(
            finding
            for finding in self.records
            if finding.object_id == object_id
            and (
                object_type is None
                or finding.object_type == object_type
            )
        )

    def add(self, finding):
        self.records.append(finding)


class _Uow:
    """Unit of Work double with shared in-memory repositories."""

    def __init__(self):
        self.discovery = _DiscoveryRepository()
        self.devices = _CanonicalRepository()
        self.findings = _FindingsRepository()


def _dataset(*observations):
    """Build a normalized synthetic source dataset."""
    return SourceDataset(
        source=Source(
            name="test_inventory",
            source_type="device_inventory",
            source_id=uuid4(),
        ),
        devices=tuple(observations),
    )


def _observation(
    serial,
    *,
    local_ref="row:1",
    name="SW-LAB-01",
    management_ip="192.0.2.10",
    **attributes,
):
    """Build a normalized synthetic device observation."""
    return DeviceObservation(
        local_ref=local_ref,
        inventory_name=name,
        hostname=name,
        serial_number=serial,
        management_ip=management_ip,
        **attributes,
    )


def _candidate(
    serial,
    *,
    name="SW-LAB-01",
    management_ip=None,
    **attributes,
):
    """Build a synthetic provisional device candidate."""
    return DeviceDiscoveryCandidate(
        name=name,
        host_name=name,
        serial_number=serial,
        management_ip=management_ip,
        **attributes,
    )


def _process(uow, *observations, dry_run=False):
    """Invoke the single public Device Processing entry point."""
    return process(
        _dataset(*observations),
        uow=uow,
        policies=_Policies(),
        dry_run=dry_run,
    )


# ------------------------------------------------------------
# Candidate creation and reuse
# ------------------------------------------------------------


def test_new_observation_creates_candidate():
    uow = _Uow()

    result = _process(
        uow,
        _observation("TEST-001"),
    )

    assert result["observations"] == 1
    assert result["candidates_created"] == 1
    assert result["candidates_reused"] == 0
    assert len(uow.discovery.candidates) == 1


def test_second_import_reuses_existing_candidate():
    uow = _Uow()

    incoming = _observation("TEST-001")

    first = _process(uow, incoming)

    original_id = next(
        iter(uow.discovery.candidates)
    )

    second = _process(uow, incoming)

    assert first["candidates_created"] == 1
    assert second["candidates_reused"] == 1
    assert second["candidates_created"] == 0

    assert len(uow.discovery.candidates) == 1
    assert original_id in uow.discovery.candidates


def test_missing_serial_is_skipped():
    uow = _Uow()

    result = _process(
        uow,
        _observation(None),
    )

    assert result["observations"] == 1
    assert result["missing_serial"] == 1
    assert result["candidates_created"] == 0
    assert not uow.discovery.candidates


@pytest.mark.parametrize(
    "serial",
    [
        "",
        " ",
        "N/A",
        "unknown",
        "null",
        "-",
        "0",
    ],
)
def test_placeholder_serial_is_skipped(serial):
    uow = _Uow()

    result = _process(
        uow,
        _observation(serial),
    )

    assert result["missing_serial"] == 1
    assert not uow.discovery.candidates


# ------------------------------------------------------------
# Exact and leading-zero serial identity
# ------------------------------------------------------------


def test_exact_serial_reuses_candidate():
    uow = _Uow()

    existing = _candidate("TEST-001")
    uow.discovery.add_candidate(existing)

    result = _process(
        uow,
        _observation("TEST-001"),
    )

    assert result["candidates_reused"] == 1
    assert result["candidates_created"] == 0
    assert existing.candidate_id in uow.discovery.candidates


def test_leading_zero_serial_reuses_candidate():
    uow = _Uow()

    existing = _candidate("00123456")
    uow.discovery.add_candidate(existing)

    result = _process(
        uow,
        _observation("123456"),
    )

    assert result["candidates_reused"] == 1
    assert result["candidates_created"] == 0
    assert len(uow.discovery.candidates) == 1
    assert existing.candidate_id in uow.discovery.candidates


def test_leading_zero_reverse_direction():
    uow = _Uow()

    existing = _candidate("123456")
    uow.discovery.add_candidate(existing)

    result = _process(
        uow,
        _observation("00123456"),
    )

    assert result["candidates_reused"] == 1
    assert result["candidates_created"] == 0
    assert len(uow.discovery.candidates) == 1


def test_arbitrary_suffix_is_not_physical_identity():
    uow = _Uow()

    existing = _candidate("ABC123456")
    uow.discovery.add_candidate(existing)

    result = _process(
        uow,
        _observation("123456"),
    )

    assert result["candidates_created"] == 1
    assert result["candidates_reused"] == 0
    assert len(uow.discovery.candidates) == 2


def test_different_numeric_serial_is_not_identity():
    uow = _Uow()

    existing = _candidate("00123457")
    uow.discovery.add_candidate(existing)

    result = _process(
        uow,
        _observation("123456"),
    )

    assert result["candidates_created"] == 1
    assert result["candidates_reused"] == 0
    assert len(uow.discovery.candidates) == 2


def test_multiple_serial_equivalent_candidates_are_ambiguous():
    uow = _Uow()

    first = _candidate(
        "00123456",
        name="SW-LAB-01",
    )
    second = _candidate(
        "000123456",
        name="SW-LAB-02",
    )

    uow.discovery.add_candidate(first)
    uow.discovery.add_candidate(second)

    result = _process(
        uow,
        _observation("123456"),
    )

    assert result["ambiguous_candidates"] == 1
    assert result["candidates_created"] == 0
    assert result["candidates_reused"] == 0
    assert len(uow.discovery.candidates) == 2


def test_rejected_candidate_is_not_reused():
    uow = _Uow()

    existing = _candidate(
        "TEST-001",
        status="rejected",
    )
    uow.discovery.add_candidate(existing)

    result = _process(
        uow,
        _observation("TEST-001"),
    )

    assert result["candidates_created"] == 1
    assert result["candidates_reused"] == 0
    assert len(uow.discovery.candidates) == 2


# ------------------------------------------------------------
# Switch stacks and shared addresses
# ------------------------------------------------------------


def test_stack_members_remain_separate():
    uow = _Uow()

    observations = tuple(
        _observation(
            serial,
            local_ref=f"stack:{index}",
            name="STACK-01",
            management_ip="192.0.2.10",
        )
        for index, serial in enumerate(
            (
                "FOC001",
                "FOC002",
                "FOC003",
            ),
            start=1,
        )
    )

    result = _process(
        uow,
        *observations,
    )

    assert result["observations"] == 3
    assert result["candidates_created"] == 3
    assert result["candidates_reused"] == 0

    assert len(uow.discovery.candidates) == 3

    stored_serials = {
        candidate.serial_number
        for candidate in uow.discovery.candidates.values()
    }

    assert stored_serials == {
        "FOC001",
        "FOC002",
        "FOC003",
    }


def test_same_hostname_and_ip_do_not_establish_identity():
    uow = _Uow()

    existing = _candidate(
        "FOC001",
        name="STACK-01",
    )
    uow.discovery.add_candidate(existing)

    result = _process(
        uow,
        _observation(
            "FOC002",
            name="STACK-01",
            management_ip="192.0.2.10",
        ),
    )

    assert result["candidates_created"] == 1
    assert result["candidates_reused"] == 0
    assert len(uow.discovery.candidates) == 2


# ------------------------------------------------------------
# Inventory attribute enrichment
# ------------------------------------------------------------


def test_new_candidate_has_inventory_attributes():
    uow = _Uow()

    incoming = _observation(
        "TEST-001",
        site="LAB-A",
        role="access_switch",
        manufacturer="Example Vendor",
        model="Example Switch",
        software_version="1.0",
        asset_tag="TEST-ASSET-001",
        primary_ipv4="192.0.2.11",
    )

    result = _process(
        uow,
        incoming,
    )

    assert result["candidates_created"] == 1
    assert result["attributes_filled"] == 7

    candidate = next(
        iter(uow.discovery.candidates.values())
    )

    assert candidate.site == "LAB-A"
    assert candidate.role == "access_switch"
    assert candidate.manufacturer == "Example Vendor"
    assert candidate.model == "Example Switch"
    assert candidate.software_version == "1.0"
    assert candidate.asset_tag == "TEST-ASSET-001"
    assert str(candidate.primary_ipv4) == "192.0.2.11"


def test_existing_candidate_fills_missing_attributes():
    uow = _Uow()

    existing = _candidate(
        "TEST-001",
        site="LAB-A",
    )
    uow.discovery.add_candidate(existing)

    result = _process(
        uow,
        _observation(
            "TEST-001",
            site="LAB-A",
            role="distribution_switch",
            model="Example Switch",
        ),
    )

    updated = uow.discovery.candidates[
        existing.candidate_id
    ]

    assert result["candidates_reused"] == 1
    assert result["candidates_enriched"] == 1
    assert result["attributes_filled"] == 2

    assert updated.site == "LAB-A"
    assert updated.role == "distribution_switch"
    assert updated.model == "Example Switch"
    assert updated.candidate_id == existing.candidate_id


def test_candidate_attribute_conflict_is_not_overwritten():
    uow = _Uow()

    existing = _candidate(
        "TEST-001",
        site="LAB-A",
    )
    uow.discovery.add_candidate(existing)

    incoming = _observation(
        "TEST-001",
        site="LAB-B",
    )

    first = _process(uow, incoming)
    second = _process(uow, incoming)

    assert first["findings_created"] == 1
    assert second["findings_created"] == 0
    assert second["findings_reused"] == 1

    assert len(uow.findings.records) == 1

    stored = uow.discovery.candidates[
        existing.candidate_id
    ]

    assert stored.site == "LAB-A"


def test_different_attribute_conflicts_create_distinct_findings():
    uow = _Uow()

    existing = _candidate(
        "TEST-001",
        site="LAB-A",
    )
    uow.discovery.add_candidate(existing)

    first = _process(
        uow,
        _observation("TEST-001", site="LAB-B"),
    )
    second = _process(
        uow,
        _observation("TEST-001", site="LAB-C"),
    )

    assert first["findings_created"] == 1
    assert second["findings_created"] == 1
    assert len(uow.findings.records) == 2


# ------------------------------------------------------------
# Dry-run behavior
# ------------------------------------------------------------


def test_dry_run_does_not_persist_candidates():
    uow = _Uow()

    result = _process(
        uow,
        _observation("TEST-001"),
        dry_run=True,
    )

    assert result["candidates_created"] == 1
    assert not uow.discovery.candidates


def test_duplicate_serial_in_one_dry_run_creates_one_proposal():
    uow = _Uow()

    result = _process(
        uow,
        _observation(
            "TEST-001",
            local_ref="row:1",
        ),
        _observation(
            "TEST-001",
            local_ref="row:2",
        ),
        dry_run=True,
    )

    assert result["observations"] == 2
    assert result["candidates_created"] == 1
    assert result["candidates_reused"] == 1

    assert not uow.discovery.candidates


def test_dry_run_enrichment_does_not_update_candidate():
    uow = _Uow()

    existing = _candidate(
        "TEST-001",
        site="LAB-A",
    )
    uow.discovery.add_candidate(existing)

    result = _process(
        uow,
        _observation(
            "TEST-001",
            site="LAB-A",
            model="Example Switch",
        ),
        dry_run=True,
    )

    assert result["candidates_enriched"] == 1
    assert result["attributes_filled"] == 1

    stored = uow.discovery.candidates[
        existing.candidate_id
    ]

    assert stored.model is None


def test_dry_run_conflict_does_not_persist_finding():
    uow = _Uow()

    existing = _candidate(
        "TEST-001",
        site="LAB-A",
    )
    uow.discovery.add_candidate(existing)

    result = _process(
        uow,
        _observation(
            "TEST-001",
            site="LAB-B",
        ),
        dry_run=True,
    )

    assert result["findings_created"] == 1
    assert uow.findings.records == []

    assert uow.discovery.candidates[
        existing.candidate_id
    ].site == "LAB-A"


# ------------------------------------------------------------
# Source authorization
# ------------------------------------------------------------


def test_unauthorized_source_is_rejected():
    uow = _Uow()

    with pytest.raises(NetVoyagerConfigError) as exc_info:
        process(
            _dataset(
                _observation("TEST-001")
            ),
            uow=uow,
            policies=_DeniedPolicies(),
        )

    assert exc_info.value.code == (
        "analysis.device_candidate_creation_not_authorized"
    )

    assert exc_info.value.details["source_id"] == (
        "test_inventory"
    )

    assert not uow.discovery.candidates


def test_exact_canonical_serial_is_detected():
    uow = _Uow()

    canonical = NetworkDevice(
        name="SW-CANONICAL-01",
        serial_number="TEST-001",
    )
    uow.devices.devices[canonical.device_id] = canonical

    result = _process(
        uow,
        _observation("TEST-001"),
    )

    assert result["canonical_matched"] == 1
    assert result["canonical_unmatched"] == 0


def test_leading_zero_canonical_serial_is_detected():
    uow = _Uow()

    canonical = NetworkDevice(
        name="SW-CANONICAL-01",
        serial_number="00123456",
    )
    uow.devices.devices[canonical.device_id] = canonical

    result = _process(
        uow,
        _observation("123456"),
    )

    assert result["canonical_matched"] == 1
    assert result["canonical_unmatched"] == 0


def test_ambiguous_canonical_serial_blocks_processing():
    uow = _Uow()

    first = NetworkDevice(
        name="SW-CANONICAL-01",
        serial_number="00123456",
    )
    second = NetworkDevice(
        name="SW-CANONICAL-02",
        serial_number="000123456",
    )

    uow.devices.devices[first.device_id] = first
    uow.devices.devices[second.device_id] = second

    result = _process(
        uow,
        _observation("123456"),
    )

    assert result["ambiguous_canonical"] == 1
    assert result["candidates_created"] == 0
    assert result["candidates_reused"] == 0