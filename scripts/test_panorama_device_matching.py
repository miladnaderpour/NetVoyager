"""Run in-memory Excel-to-Panorama physical-device reconciliation.

This diagnostic uses real parsed exports and configured source policies. It
never modifies input files or a persistent inventory. Identity matching uses
domain objects; evidence is retained separately for audit decisions.
"""

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from netvoyager_analysis.attributes.store import AttributeAssertionStore
from netvoyager_analysis.devices.attribute_reconciliation import (
    DeviceAttributeReconciliationService,
)
from netvoyager_analysis.devices.candidate_matching import IdentityTarget
from netvoyager_analysis.devices.discovery.models import DeviceDiscoveryCandidate
from netvoyager_network.device.discovery.store import DeviceDiscoveryStore
from netvoyager_analysis.devices.identity_validation import IdentityValidator
from netvoyager_analysis.devices.matching_rules import SourceRef
from netvoyager_analysis.devices.reconciliation import DeviceReconciliationService
from netvoyager_analysis.evidence.models import EvidenceRecord
from netvoyager_analysis.evidence.store import EvidenceStore
from netvoyager_analysis.paloalto.adapters import adapt_panorama_firewall
from netvoyager_analysis.policies.engine import PolicyEngine
from netvoyager_core.config import LoggingSettings
from netvoyager_core.logging import get_logger, setup_logging
from netvoyager_import.inventory.excel import read_network_devices
from netvoyager_paloalto.inventory.parser import parse_panorama_inventory

logger = get_logger("netvoyager.scripts.test_panorama_device_matching")
EXCEL = SourceRef("excel_inventory", "device_inventory")
PANORAMA = SourceRef("paloalto_panorama", "managed_device_inventory")


def _excel_candidates(observations, evidence_store, discovery_store):
    """Register independent Excel candidates and retain source observations."""
    sources = {}
    for observation in observations:
        candidate = DeviceDiscoveryCandidate(
            name=observation.name,
            host_name=observation.host_name,
            serial_number=observation.serial_number,
            management_ip=observation.management_ip,
        )
        discovery_store.add_candidate(candidate)
        sources[candidate.candidate_id] = EXCEL
        record = EvidenceRecord(
            source=EXCEL.source_id,
            details={
                "method": EXCEL.method,
                "name": observation.name,
                "host_name": observation.host_name,
                "serial_number": observation.serial_number,
                "management_ip": observation.management_ip,
                "line_number": observation.line_number,
            },
        )
        evidence_store.add(record)
        evidence_store.link(record.id, "device_discovery_candidate", candidate.candidate_id)
    return sources


def _firewall_identity(firewall, evidence_store):
    """Adapt a firewall and record provenance separately from matching."""
    observation = adapt_panorama_firewall(firewall)
    record = EvidenceRecord(
        source=PANORAMA.source_id,
        details={
            "method": PANORAMA.method,
            "name": observation.name,
            "host_name": observation.host_name,
            "serial_number": observation.serial_number,
            "management_ip": observation.management_ip,
        },
    )
    evidence_store.add(record)
    # Provisional object is only an input to matching; it is not registered
    # as an extra Panorama candidate when a trusted identity can be promoted.
    provisional = DeviceDiscoveryCandidate(
        name=observation.name,
        host_name=observation.host_name,
        serial_number=observation.serial_number,
        management_ip=observation.management_ip,
    )
    return observation, IdentityTarget(provisional, PANORAMA), record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inventory", type=Path, help="Master inventory XLSX")
    parser.add_argument("panorama", type=Path, help="Panorama inventory JSON")
    parser.add_argument("--sheet", help="Worksheet name (default: active)")
    parser.add_argument(
        "--policies", type=Path, default=Path("examples/policies"),
        help="Directory of existing source trust YAML policies",
    )
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    log_path = Path("logs") / (
        f"panorama_device_matching_{datetime.now():%Y%m%d_%H%M%S_%f}.log"
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    level = "DEBUG" if args.debug else "INFO"
    setup_logging(LoggingSettings(targets_json=json.dumps([
        {"name": "console", "output": "stdout", "level": level, "format": "text"},
        {"name": "file", "output": "file", "level": level,
         "format": "text", "file_path": str(log_path)},
    ])))

    policy_engine = PolicyEngine()
    try:
        policy_engine.load_directory(args.policies)
        for source in (EXCEL, PANORAMA):
            if policy_engine.get(source.source_id, source.method) is None:
                raise ValueError(f"Missing source policy: {source}")
        inventory = read_network_devices(args.inventory, sheet_name=args.sheet)
        panorama = parse_panorama_inventory(
            args.panorama.read_text(encoding="utf-8-sig")
        )
    except (OSError, UnicodeError, ValueError) as exc:
        logger.error("Cannot load input or policies: %s", exc)
        return 1

    evidence_store = EvidenceStore()
    discovery_store = DeviceDiscoveryStore()
    assertion_store = AttributeAssertionStore(evidence_store=evidence_store)
    validator = IdentityValidator()
    reconciliation = DeviceReconciliationService(
        discovery_store=discovery_store,
        policy_engine=policy_engine,
        validator=validator,
    )
    attributes = DeviceAttributeReconciliationService(
        assertion_store=assertion_store, policy_engine=policy_engine,
    )
    candidate_sources = _excel_candidates(
        inventory.observations, evidence_store, discovery_store,
    )
    canonical_devices = {}
    counts: Counter[str] = Counter()
    counts["excel_candidates"] = len(discovery_store.candidates)
    counts["panorama_firewalls"] = len(panorama.firewalls)
    counts["parser_issues"] = len(panorama.issues)
    counts["collection_failures"] = len(panorama.collection_failures)
    counts["inventory_issues"] = len(inventory.issues)

    for firewall in panorama.firewalls:
        observation, target, record = _firewall_identity(firewall, evidence_store)
        display = observation.host_name or observation.name or "<unnamed>"
        identity = validator.validate_canonical_identity(
            target, canonical_devices=canonical_devices.values(),
        )
        try:
            result = reconciliation.reconcile(
                target,
                canonical_devices=canonical_devices,
                evidence_ids=(record.id,),
                candidate_sources=candidate_sources,
                name=display,
            )
        except (ValueError, PermissionError) as exc:
            counts["reconciliation_blocked"] += 1
            logger.warning(
                "BLOCKED: firewall=%s serial=%s reason=%s",
                display, observation.serial_number, exc,
            )
            continue

        counts["canonical_created" if result.created else "canonical_reused"] += 1
        counts["excel_candidates_resolved"] += len(result.resolved_candidate_ids)
        evidence_store.link(record.id, "network_device", result.device.device_id)
        for candidate_id in result.resolved_candidate_ids:
            # The discovery store already records the source observation UUID
            # in the candidate resolution decision; preserve candidate evidence.
            logger.info("RESOLVED: candidate_id=%s device_id=%s", candidate_id, result.device.device_id)
        attr = attributes.reconcile_host_name(
            result.device, observation.host_name,
            source=PANORAMA, evidence_ids=(record.id,), identity=identity,
        )
        counts[f"hostname_{attr.status}"] += 1
        logger.info(
            "%s: panorama=%s serial=%s device=%s id=%s resolved=%d host_name=%s",
            "CREATED" if result.created else "REUSED",
            display, observation.serial_number, result.device.name,
            result.device.device_id, len(result.resolved_candidate_ids), attr.status,
        )

    counts["unresolved_excel_candidates"] = sum(
        candidate.resolved_device_id is None
        for candidate in discovery_store.candidates
    )
    counts["canonical_total"] = len(canonical_devices)
    counts["discovery_decisions"] = len(discovery_store.decisions)
    counts["attribute_assertions"] = len(assertion_store.assertions)
    counts["attribute_decisions"] = len(assertion_store.decisions)
    counts["evidence_records"] = len(evidence_store.records)
    for key, value in sorted(counts.items()):
        logger.info("SUMMARY: %s=%d", key, value)
    logger.info("Diagnostic complete; no input files or persistent stores changed")
    logger.info("Log file: %s", log_path.resolve())
    return 0 if not counts["reconciliation_blocked"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
