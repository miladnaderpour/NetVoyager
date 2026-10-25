
"""Process normalized device observations through V1 discovery.

Public entry point: process().

The processor uses the existing Unit of Work repositories and
PolicyEngine. It never commits the caller-owned transaction.

Canonical creation and resolution remain with the existing
authorized reconciliation mechanism.
"""

from __future__ import annotations

from collections import Counter
from ipaddress import IPv4Address, AddressValueError

from netvoyager_core.exceptions import (
    NetVoyagerConfigError,
    NetVoyagerError,
)
from netvoyager_core.logging import get_logger

from netvoyager_analysis.devices.candidate_enrichment import (
    enrich_device_candidate,
)
from netvoyager_analysis.devices.candidate_enrichment_workflow import (
    persist_candidate_enrichment,
)
from netvoyager_analysis.devices.matching_rules import SourceRef
from netvoyager_analysis.policies.engine import PolicyEngine
from netvoyager_analysis.protocols.unit_of_work import UnitOfWorkProtocol
from netvoyager_analysis.sources.models import SourceDataset

from netvoyager_network.device.discovery.models import (
    DeviceDiscoveryCandidate,
)


logger = get_logger(__name__)

_INVALID_SERIALS = frozenset({
    "", "n/a", "na", "none", "null", "unknown", "0", "-",
})


def _serial(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None

    value = value.strip()

    if value.casefold() in _INVALID_SERIALS:
        return None

    return value


def _serial_equivalent(left: str | None, right: str | None) -> bool:
    """Require exact correspondence or numeric leading-zero loss."""
    a = _serial(left)
    b = _serial(right)

    if a is None or b is None:
        return False

    if a.casefold() == b.casefold():
        return True

    if not (
        a.isascii()
        and b.isascii()
        and a.isdecimal()
        and b.isdecimal()
    ):
        return False

    normalized_a = a.lstrip("0")
    normalized_b = b.lstrip("0")

    return bool(normalized_a) and normalized_a == normalized_b


def _find_candidates(serial: str, repository) -> tuple:
    """Find all active, serial-equivalent candidates.

    Exact lookup is performed first. Suffix queries discover possible
    leading-zero variants; every returned record is validated.
    """
    matches = {}

    for candidate in repository.find_by_serial(serial):
        if (
            candidate.status not in {"rejected", "retired"}
            and _serial_equivalent(serial, candidate.serial_number)
        ):
            matches[candidate.candidate_id] = candidate

    if serial.isascii() and serial.isdecimal():
        suffix = serial.lstrip("0")

        if suffix:
            for candidate in repository.find_by_serial_suffix(suffix):
                if (
                    candidate.status not in {"rejected", "retired"}
                    and _serial_equivalent(
                        serial,
                        candidate.serial_number,
                    )
                ):
                    matches[candidate.candidate_id] = candidate

    return tuple(matches.values())


def _find_canonical(
    serial: str,
    repository,
) -> tuple:
    """Find canonical identities using exact and leading-zero serials.

    A database suffix match is only a search result.
    Physical identity is established by serial equivalence.
    """
    matches = {}

    for device in repository.find_by_serial(serial):
        if _serial_equivalent(serial, device.serial_number):
            matches[device.device_id] = device

    if serial.isascii() and serial.isdecimal():
        suffix = serial.lstrip("0")

        if suffix:
            for device in repository.find_by_serial_suffix(suffix):
                if _serial_equivalent(
                    serial,
                    device.serial_number,
                ):
                    matches[device.device_id] = device

    return tuple(matches.values())


def _ipv4(value: str | None) -> IPv4Address | None:
    """Convert optional IPv4 input using a structured NetVoyager error."""
    if not value:
        return None

    try:
        return IPv4Address(value)
    except (AddressValueError, ValueError) as exc:
        raise NetVoyagerError(
            code="analysis.device_invalid_ipv4",
            message="Invalid observed device IPv4 address.",
            details={"value": str(value)},
        ) from exc


def process(
    dataset: SourceDataset,
    *,
    uow: UnitOfWorkProtocol,
    policies: PolicyEngine,
    dry_run: bool = False,
) -> Counter[str]:
    """Process device observations into discovery candidates and findings.

    The caller supplies an active Unit of Work and owns commit/rollback.
    Dry-run evaluates the batch without writing any records.

    Canonical matching currently uses exact serial lookup. Canonical
    mutation is deliberately not performed here until the authorized
    reconciliation path is integrated with the SQL repositories.
    """
    counts: Counter[str] = Counter()

    source = SourceRef(
        source_id=dataset.source.name,
        method=dataset.source.source_type,
    )

    permission = policies.evaluate(
        source.source_id,
        source.method,
        claim="device.physical_identity",
        action="create_candidate",
    )

    if not permission.allowed:
        raise NetVoyagerConfigError(
            code="analysis.device_candidate_creation_not_authorized",
            message="Source is not authorized for device discovery.",
            details={
                "source_id": source.source_id,
                "source_method": source.method,
            },
        )

    # Tracks newly created and enriched candidates within this batch.
    # This also permits proper repeated-row simulation in dry-run.
    batch_candidates: dict[str, DeviceDiscoveryCandidate] = {}

    # Tracks conflict Findings proposed during this dry run, avoiding
    # double counting when a workbook repeats the same observation.
    dry_run_conflicts: set[tuple] = set()

    for observation in dataset.devices:
        counts["observations"] += 1

        serial = _serial(observation.serial_number)

        if serial is None:
            counts["missing_serial"] += 1
            continue

        # -----------------------------------------------------
        # 1. Canonical identity lookup
        # -----------------------------------------------------
        canonical_matches = _find_canonical(serial, uow.devices)

        if len(canonical_matches) > 1:
            counts["ambiguous_canonical"] += 1
            logger.warning(
                "Ambiguous canonical device serial identity",
                extra={"local_ref": observation.local_ref},
            )
            continue

        canonical = canonical_matches[0] if canonical_matches else None

        if canonical is not None:
            counts["canonical_matched"] += 1
        else:
            counts["canonical_unmatched"] += 1

        # -----------------------------------------------------
        # 2. Candidate identity lookup
        # -----------------------------------------------------
        candidates = {
            item.candidate_id: item
            for item in _find_candidates(serial, uow.discovery)
        }

        for item in batch_candidates.values():
            if _serial_equivalent(serial, item.serial_number):
                candidates[item.candidate_id] = item

        if len(candidates) > 1:
            counts["ambiguous_candidates"] += 1
            logger.warning(
                "Ambiguous device discovery candidate identity",
                extra={"local_ref": observation.local_ref},
            )
            continue

        # -----------------------------------------------------
        # 3. Reuse or create provisional candidate
        # -----------------------------------------------------
        if candidates:
            candidate = next(iter(candidates.values()))

            # An already resolved candidate cannot point to a
            # different canonical identity.
            if (
                candidate.status == "resolved"
                and canonical is not None
                and candidate.resolved_device_id != canonical.device_id
            ):
                counts["resolution_conflicts"] += 1
                continue

            counts["candidates_reused"] += 1

            # -------------------------------------------------
            # 4. Candidate enrichment + conflict Findings
            # -------------------------------------------------
            if dry_run:
                proposal = enrich_device_candidate(
                    candidate,
                    observation,
                    source=source,
                )

                changed_fields = proposal.changed_fields
                updated = proposal.candidate

                existing = uow.findings.for_object(
                    candidate.candidate_id,
                    object_type="device_discovery_candidate",
                )

                from netvoyager_analysis.devices.candidate_enrichment_workflow import (
                    _conflict_key,
                )

                known_keys = {
                    _conflict_key(item)
                    for item in existing
                    if item.kind == "device_candidate_attribute_conflict"
                }

                for finding in proposal.findings:
                    key = _conflict_key(finding)

                    if key in known_keys or key in dry_run_conflicts:
                        counts["findings_reused"] += 1
                    else:
                        counts["findings_created"] += 1
                        dry_run_conflicts.add(key)
            else:
                result = persist_candidate_enrichment(
                    candidate,
                    observation,
                    source=source,
                    candidates=uow.discovery,
                    findings=uow.findings,
                )

                changed_fields = result.changed_fields
                updated = result.candidate
                counts["findings_created"] += len(result.new_findings)
                counts["findings_reused"] += result.duplicate_findings

            counts["attributes_filled"] += len(changed_fields)

            if changed_fields:
                counts["candidates_enriched"] += 1

            batch_candidates[str(updated.candidate_id)] = updated

        else:
            candidate = DeviceDiscoveryCandidate(
                name=observation.inventory_name or observation.hostname,
                host_name=observation.hostname,
                serial_number=serial,
                management_ip=_ipv4(observation.management_ip),
            )

            enriched = enrich_device_candidate(
                candidate,
                observation,
                source=source,
            )

            candidate = enriched.candidate

            if not dry_run:
                uow.discovery.add_candidate(candidate)

            batch_candidates[str(candidate.candidate_id)] = candidate

            counts["candidates_created"] += 1
            counts["attributes_filled"] += len(enriched.changed_fields)

        # -----------------------------------------------------
        # 5. Canonical reconciliation boundary
        # -----------------------------------------------------
        # We intentionally report this pending action instead of
        # bypassing the existing identity authorization and audit.
        if canonical is not None:
            counts["candidates_pending_resolution_check"] += 1
        else:
            counts["candidates_pending_canonical_policy"] += 1

    return counts
