"""Convert source-specific issues into analysis findings."""

from collections.abc import Iterable

from netvoyager_import.inventory.excel import InventoryIssue
from netvoyager_paloalto.inventory.models import PanoramaImportIssue

from .models import Finding
from .store import FindingStore


def add_inventory_issues(
    issues: Iterable[InventoryIssue],
    *,
    finding_store: FindingStore,
) -> tuple[Finding, ...]:
    """Convert inventory import issues into analysis findings."""
    findings: list[Finding] = []

    for issue in issues:
        finding = Finding(
            kind="inventory_issue",
            severity="warning",
            message=issue.reason,
            object_type="inventory_row",
            object_id=str(issue.row_number),
            details={
                "row_number": issue.row_number,
                "reason": issue.reason,
            },
        )

        finding_store.add(finding)
        findings.append(finding)

    return tuple(findings)


def add_panorama_issues(
    issues: Iterable[PanoramaImportIssue],
    *,
    finding_store: FindingStore,
) -> tuple[Finding, ...]:
    """Convert Panorama import issues into analysis findings."""
    findings: list[Finding] = []

    for issue in issues:
        finding = Finding(
            kind="panorama_issue",
            severity=issue.severity,
            message=issue.reason,
            object_type=(
                "panorama_firewall"
                if issue.firewall_serial is not None
                else "panorama_inventory"
            ),
            object_id=issue.firewall_serial,
            details={
                "path": issue.path,
                "reason": issue.reason,
                "firewall_serial": issue.firewall_serial,
                "raw_value_json": issue.raw_value_json,
            },
        )

        finding_store.add(finding)
        findings.append(finding)

    return tuple(findings)