
"""Persist Panorama observations and reconcile canonical prefixes in SQLite.

AddressSpace mapping comes from an explicit configuration file.
Unmapped prefixes remain observations/candidates without canonical promotion.

This is a disposable SQLite integration diagnostic.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import replace
from datetime import datetime, timezone
from ipaddress import IPv4Address
from pathlib import Path

from sqlalchemy import func, select

from import_panorama import (
    import_panorama,
    load_address_space_mapping,
)

from netvoyager_analysis.ipam.discovery.assignment import (
    PrefixObservationAssignmentService,
)
from netvoyager_analysis.ipam.discovery.persistent_correlation import (
    PrefixCandidateCorrelationService,
)
from netvoyager_analysis.ipam.discovery.reconciliation import (
    PrefixReconciliationService,
)
from netvoyager_analysis.policies.engine import PolicyEngine
from netvoyager_analysis.sources.models import SourceDataset

from netvoyager_core.config import LoggingSettings
from netvoyager_core.logging import get_logger, setup_logging

from netvoyager_database.engine import create_database_engine
from netvoyager_database.schema import create_schema
from netvoyager_database.session import create_session_factory
from netvoyager_database.unit_of_work.network_inventory import (
    NetworkInventoryUnitOfWork,
)

from netvoyager_database.entities.devices.network_device import (
    NetworkDeviceEntity,
)
from netvoyager_database.entities.devices.discovery_candidate import (
    DeviceDiscoveryCandidateEntity,
)
from netvoyager_database.entities.ipam import (
    PrefixObservationEntity,
    PrefixDiscoveryCandidateEntity,
    NetworkPrefixEntity,
)

from netvoyager_network.device.models import NetworkDevice
from netvoyager_network.device.discovery.models import (
    DeviceDiscoveryCandidate,
)
from netvoyager_network.device.discovery.decisions import (
    DeviceDiscoveryDecision,
)
from netvoyager_network.ipam.address_space import GLOBAL_ADDRESS_SPACE


logger = get_logger("scripts.persist_panorama")


def configure_logging(debug: bool) -> None:
    """Configure console and file logging through netvoyager-core."""
    level = "DEBUG" if debug else "INFO"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

    path = Path("logs") / f"panorama_persistence_{timestamp}.log"
    path.parent.mkdir(parents=True, exist_ok=True)

    setup_logging(
        LoggingSettings(
            targets_json=json.dumps(
                [
                    {
                        "name": "console",
                        "output": "stdout",
                        "level": level,
                        "format": "text",
                    },
                    {
                        "name": "file",
                        "output": "file",
                        "file_path": str(path),
                        "level": level,
                        "format": "text",
                    },
                ]
            )
        )
    )

    logger.info(
        "Persistence diagnostic logging initialized",
        extra={"log_file": str(path)},
    )


def count_rows(uow: NetworkInventoryUnitOfWork) -> dict[str, int]:
    """Read actual database row counts."""
    tables = {
        "canonical_devices": NetworkDeviceEntity,
        "device_candidates": DeviceDiscoveryCandidateEntity,
        "prefix_observations": PrefixObservationEntity,
        "prefix_candidates": PrefixDiscoveryCandidateEntity,
        "canonical_prefixes": NetworkPrefixEntity,
    }

    return {
        name: uow.session.scalar(
            select(func.count()).select_from(entity)
        ) or 0
        for name, entity in tables.items()
    }


def authorize(
    policies: PolicyEngine,
    dataset: SourceDataset,
    *,
    claim: str,
    action: str,
    requirements: dict[str, bool] | None = None,
) -> tuple[bool, int]:
    """Evaluate the configured source policy."""
    result = policies.evaluate(
        dataset.source.name,
        dataset.source.source_type,
        claim=claim,
        action=action,
        requirements=requirements,
    )

    logger.debug(
        "Policy evaluated",
        extra={
            "claim": claim,
            "action": action,
            "allowed": result.allowed,
            "authority": result.authority,
            "reason": result.reason,
            "policy_version": result.policy_version,
        },
    )

    return result.allowed, result.policy_version


def process_devices(
    uow: NetworkInventoryUnitOfWork,
    dataset: SourceDataset,
    policies: PolicyEngine,
    counts: Counter[str],
) -> None:
    """Persist device candidates and authorized canonical devices."""
    for observation in dataset.devices:
        serial = (
            observation.serial_number.strip()
            if observation.serial_number
            else None
        )

        name = observation.inventory_name or observation.hostname
        name = name.strip() if name else None

        if not serial:
            counts["device_missing_serial"] += 1
            logger.warning(
                "Device lacks a serial number",
                extra={"local_ref": observation.local_ref},
            )
            continue

        matching_candidates = uow.discovery.find_by_serial(serial)

        active = [
            item
            for item in matching_candidates
            if item.status not in {"rejected", "retired"}
        ]

        if len(active) > 1:
            counts["device_ambiguous"] += 1
            logger.warning(
                "Multiple device candidates have the same serial",
                extra={
                    "serial": serial,
                    "candidate_count": len(active),
                },
            )
            continue

        if active:
            candidate = active[0]
            counts["device_candidate_reused"] += 1
        else:
            allowed, _ = authorize(
                policies,
                dataset,
                claim="device.physical_identity",
                action="create_candidate",
            )

            if not allowed:
                counts["device_candidate_denied"] += 1
                continue

            candidate = DeviceDiscoveryCandidate(
                name=name,
                host_name=observation.hostname,
                serial_number=serial,
                management_ip=(
                    IPv4Address(observation.management_ip)
                    if observation.management_ip
                    else None
                ),
            )

            uow.discovery.add_candidate(candidate)
            counts["device_candidate_created"] += 1

        canonical_matches = uow.devices.find_by_serial(serial)

        if len(canonical_matches) > 1:
            counts["device_canonical_ambiguous"] += 1
            continue

        canonical = (
            canonical_matches[0]
            if canonical_matches
            else None
        )

        if canonical is None and name:
            by_name = uow.devices.find_by_name(name)

            if by_name is not None and by_name.serial_number != serial:
                counts["device_name_conflict"] += 1
                logger.warning(
                    "Canonical name belongs to a different serial",
                    extra={
                        "device_name": name,
                        "serial": serial,
                    },
                )
                continue

        requirements = {
            "unique_physical_serial": True,
            "unambiguous_device_match": True,
            "verified_device_identity": True,
        }

        action = (
            "promote_candidate"
            if canonical is not None
            else "create_canonical_device"
        )

        allowed, version = authorize(
            policies,
            dataset,
            claim="device.physical_identity",
            action=action,
            requirements=requirements,
        )

        if not allowed:
            counts["device_canonical_denied"] += 1
            continue

        if canonical is None:
            if not name:
                counts["device_missing_name"] += 1
                continue

            canonical = NetworkDevice(
                name=name,
                serial_number=serial,
                host_name=observation.hostname,
                manufacturer=observation.manufacturer,
                model=observation.model,
                software_version=observation.software_version,
                management_ip=(
                    IPv4Address(observation.management_ip)
                    if observation.management_ip
                    else None
                ),
            )

            uow.devices.add(canonical)
            counts["device_canonical_created"] += 1
        else:
            counts["device_canonical_reused"] += 1

        if candidate.status == "resolved":
            if candidate.resolved_device_id != canonical.device_id:
                raise ValueError(
                    "Device candidate already resolved to another identity"
                )
            continue

        allowed, promotion_version = authorize(
            policies,
            dataset,
            claim="device.physical_identity",
            action="promote_candidate",
            requirements=requirements,
        )

        if not allowed:
            counts["device_promotion_denied"] += 1
            continue

        uow.discovery.save_candidate(
            replace(
                candidate,
                status="resolved",
                resolved_device_id=canonical.device_id,
            )
        )

        uow.discovery.append_decision(
            DeviceDiscoveryDecision(
                decision_type="candidate_resolution",
                subject_type="candidate",
                subject_id=candidate.candidate_id,
                previous_value=None,
                new_value=str(canonical.device_id),
                evidence_ids=(),
                reason="Panorama policy-authorized identity resolution",
                timestamp=datetime.now(timezone.utc),
                source_id=dataset.source.name,
                method=dataset.source.source_type,
                policy_version=promotion_version or version,
                actor_type="system",
                actor_id="panorama-persistence-diagnostic",
            )
        )

        counts["device_candidate_resolved"] += 1


def register_address_spaces(
    uow: NetworkInventoryUnitOfWork,
    dataset: SourceDataset,
) -> None:
    """Register known AddressSpaces used by imported observations."""
    used_ids = {
        observation.address_space_id
        for observation in dataset.network_prefixes
        if observation.address_space_id is not None
    }

    supported_spaces = {
        GLOBAL_ADDRESS_SPACE.id: GLOBAL_ADDRESS_SPACE,
    }

    for address_space_id in used_ids:
        address_space = supported_spaces.get(address_space_id)

        if address_space is None:
            raise ValueError(
                f"Imported AddressSpace is not registered: "
                f"{address_space_id}"
            )

        if uow.network_prefixes.get_address_space(
            address_space_id
        ) is None:
            uow.network_prefixes.add_address_space(address_space)

            logger.info(
                "AddressSpace registered",
                extra={
                    "address_space_id": str(address_space_id),
                    "address_space_name": address_space.name,
                },
            )


def process_prefixes(
    uow: NetworkInventoryUnitOfWork,
    dataset: SourceDataset,
    policies: PolicyEngine,
    counts: Counter[str],
) -> None:
    """Persist all observations and reconcile only mapped prefixes."""
    assignment = PrefixObservationAssignmentService(uow)
    correlation = PrefixCandidateCorrelationService(uow)
    reconciliation = PrefixReconciliationService(uow, policies)

    register_address_spaces(uow, dataset)

    requirements = {
        "valid_network_prefix": True,
        "verified_reporting_source": True,
    }

    for observation in dataset.network_prefixes:
        plan = assignment.assign(
            observation,
            dataset_id=dataset.dataset_id,
            source=dataset.source,
        )

        counts["prefix_observation_persisted"] += 1
        counts[f"prefix_{plan.action}"] += 1

        result = correlation.correlate(
            observation.prefix.with_prefixlen
        )

        counts["prefix_relationship_proposed"] += len(
            result.proposed
        )

        if observation.address_space_id is None:
            counts["prefix_unmapped"] += 1
            continue

        counts["prefix_mapped"] += 1

        existing = uow.network_prefixes.find_prefix(
            observation.prefix.with_prefixlen,
            observation.address_space_id,
        )

        action = (
            "promote_candidate"
            if existing is not None
            else "create_canonical_prefix"
        )

        allowed, _ = authorize(
            policies,
            dataset,
            claim="prefix.existence",
            action=action,
            requirements=requirements,
        )

        if not allowed:
            counts["prefix_canonical_denied"] += 1

            logger.warning(
                "Canonical prefix creation denied by policy",
                extra={
                    "prefix": observation.prefix.with_prefixlen,
                    "action": action,
                    "source_name": dataset.source.name,
                    "source_method": dataset.source.source_type,
                },
            )
            continue

        try:
            canonical = reconciliation.reconcile(
                candidate_id=plan.candidate.candidate_id,
                observation_id=observation.observation_id,
                actor_type="system",
                actor_id="panorama-persistence-diagnostic",
                requirements=requirements,
            )
        except PermissionError:
            counts["prefix_canonical_denied"] += 1

            logger.exception(
                "Canonical prefix reconciliation denied",
                extra={
                    "prefix": observation.prefix.with_prefixlen,
                    "address_space_id": str(
                        observation.address_space_id
                    ),
                },
            )
            continue

        if canonical is None:
            raise RuntimeError(
                "Reconciliation returned no canonical NetworkPrefix "
                f"for {observation.prefix.with_prefixlen}"
            )

        if existing is None:
            counts["prefix_canonical_created"] += 1
        else:
            counts["prefix_canonical_reused"] += 1

        counts["prefix_candidate_resolved"] += 1

        logger.debug(
            "Prefix reconciled",
            extra={
                "prefix": canonical.prefix.with_prefixlen,
                "canonical_id": str(canonical.id),
                "candidate_id": str(plan.candidate.candidate_id),
                "address_space_id": str(
                    observation.address_space_id
                ),
            },
        )


def main() -> int:
    """Run the Panorama-to-SQLite integration diagnostic."""
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument("export", type=Path)

    parser.add_argument(
        "--database",
        type=Path,
        default=Path("output/panorama-diagnostic.db"),
    )

    parser.add_argument(
        "--policies",
        type=Path,
        default=Path("examples/policies"),
    )

    parser.add_argument(
        "--address-space-config",
        type=Path,
        default=None,
        help="YAML file containing explicit VR-to-AddressSpace mappings",
    )

    parser.add_argument("--debug", action="store_true")

    args = parser.parse_args()
    configure_logging(args.debug)

    if args.database.exists():
        logger.error(
            "Diagnostic database already exists; refusing to overwrite it",
            extra={"database": str(args.database)},
        )
        return 2

    engine = None

    try:
        mapping = load_address_space_mapping(
            args.address_space_config
        )

        logger.info(
            "AddressSpace configuration loaded",
            extra={
                "configuration": (
                    str(args.address_space_config)
                    if args.address_space_config is not None
                    else None
                ),
                "mapped_virtual_routers": len(mapping),
            },
        )

        dataset, parser_counts = import_panorama(
            args.export,
            address_space_mapping=mapping,
        )

        if (
            args.address_space_config is not None
            and parser_counts["prefix_mapped"] == 0
        ):
            raise ValueError(
                "AddressSpace configuration matched no prefixes; "
                "refusing an empty canonical import"
            )

        policies = PolicyEngine()
        policies.load_directory(args.policies)

        if policies.get(
            dataset.source.name,
            dataset.source.source_type,
        ) is None:
            raise ValueError(
                "No registered policy for Panorama inventory source"
            )

        args.database.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        engine = create_database_engine(
            f"sqlite:///{args.database.resolve().as_posix()}"
        )

        create_schema(engine)
        session_factory = create_session_factory(engine)

        counts: Counter[str] = Counter()

        with NetworkInventoryUnitOfWork(session_factory) as uow:
            process_devices(
                uow,
                dataset,
                policies,
                counts,
            )

            process_prefixes(
                uow,
                dataset,
                policies,
                counts,
            )

            if (
                parser_counts["prefix_mapped"] > 0
                and counts["prefix_canonical_created"] == 0
                and counts["prefix_canonical_reused"] == 0
            ):
                raise RuntimeError(
                    "Mapped prefixes were imported, but none were "
                    "reconciled into canonical NetworkPrefix records. "
                    "Check the Panorama prefix.existence policy."
                )

            uow.commit()

        with NetworkInventoryUnitOfWork(session_factory) as uow:
            persisted = count_rows(uow)

        logger.info(
            "Panorama SQLite persistence verified",
            extra={
                "database": str(args.database),
                "dataset_id": str(dataset.dataset_id),
                "source_name": dataset.source.name,
                "source_method": dataset.source.source_type,
                "input_devices": len(dataset.devices),
                "input_prefixes": len(dataset.network_prefixes),
                "parser_mapped_prefixes": parser_counts["prefix_mapped"],
                "parser_unmapped_prefixes": parser_counts["prefix_unmapped"],
                "parser_issues": parser_counts["parser_issues"],
                **dict(sorted(counts.items())),
                **persisted,
            },
        )

        return 0

    except Exception as exc:
        import traceback

        logger.error(
            "Panorama persistence diagnostic failed",
            extra={
                "database": str(args.database),
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "traceback": traceback.format_exc(),
            },
        )
        return 1

    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
