"""Read the *normalized* LogicMonitor inventory as a source-neutral dataset.

No ORM, identity matching, deduplication, or canonical decisions occur here.
Each accepted worksheet row remains a separate ImportDevice observation.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from ipaddress import ip_address
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from pydantic import ValidationError
from netvoyager_schemas.imports import ImportDevice, SourceDataset


REQUIRED_COLUMNS = (
    "Resource Name", "Source Excel Row", "Normalized Name",
    "Normalized Management IP", "Normalized Serial",
)
PRESERVED_COLUMNS = (
    "Alerting status", "Resource Name", "IP Address", "OS Version",
    "MAC Address", "Serial Number", "Collector Group", "Collector Name",
    "Groups", "Normalized Name", "Normalized Management IP",
    "Embedded Name IP", "Normalized Serial", "Normalized MAC",
    "Review Status", "Review Issues", "Original Resource Name",
)


@dataclass(frozen=True, slots=True)
class ImportIssue:
    excel_row: int
    source_excel_row: str
    severity: str
    code: str
    message: str

    def as_dict(self) -> dict[str, Any]:
        return dict(excel_row=self.excel_row, source_excel_row=self.source_excel_row,
                    severity=self.severity, code=self.code, message=self.message)


@dataclass(frozen=True, slots=True)
class ImportResult:
    dataset: SourceDataset
    issues: tuple[ImportIssue, ...]
    total_rows: int
    rejected_rows: int

    def report(self) -> dict[str, Any]:
        return {
            "source_id": self.dataset.source_id,
            "collected_at": self.dataset.collected_at.isoformat(),
            "total_rows": self.total_rows,
            "imported_rows": len(self.dataset.devices),
            "rejected_rows": self.rejected_rows,
            "warnings": sum(x.severity == "warning" for x in self.issues),
            "issues": [x.as_dict() for x in self.issues],
        }


def _text(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def _valid_ip(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return str(ip_address(value))
    except ValueError:
        return None


def read_logicmonitor_excel(
    path: str | Path,
    *,
    collected_at: datetime,
    source_id: str = "logicmonitor:excel",
) -> ImportResult:
    """Convert a normalized inventory to SourceDataset and row-level issues.

    ``collected_at`` is required: file modification time is NOT collection time.
    Invalid IP is kept in source_attributes; missing serials stay observations.
    """
    path = Path(path)
    if collected_at.tzinfo is None or collected_at.utcoffset() is None:
        raise ValueError("collected_at must be timezone-aware")

    wb = load_workbook(path, read_only=True, data_only=True)
    try:
        if "Inventory" not in wb.sheetnames:
            raise ValueError("Expected normalized workbook with 'Inventory' worksheet")
        ws = wb["Inventory"]
        rows = ws.iter_rows(values_only=True)
        headers = next(rows, None)
        if not headers:
            raise ValueError("Inventory worksheet has no header")
        indexes = {str(cell).strip(): idx for idx, cell in enumerate(headers) if cell is not None}
        missing = sorted(set(REQUIRED_COLUMNS) - set(indexes))
        if missing:
            raise ValueError("Missing normalized columns: " + ", ".join(missing))

        devices: list[ImportDevice] = []
        issues: list[ImportIssue] = []
        total_rows = 0
        rejected = 0
        seen_refs: set[str] = set()
        for excel_row, values in enumerate(rows, start=2):
            if not any(_text(v) is not None for v in values):
                continue
            total_rows += 1
            def get(col: str) -> Any:
                idx = indexes.get(col)
                return values[idx] if idx is not None and idx < len(values) else None

            source_row = _text(get("Source Excel Row")) or str(excel_row)
            # A row number is scoped to this export; not a stable LM resource ID.
            source_ref = f"row:{source_row}"
            if source_ref in seen_refs:
                issues.append(ImportIssue(excel_row, source_row, "error", "DUPLICATE_ROW_REFERENCE", source_ref))
                rejected += 1
                continue
            seen_refs.add(source_ref)

            name = _text(get("Normalized Name"))
            serial = _text(get("Normalized Serial"))
            ip_raw = _text(get("Normalized Management IP"))
            ip = _valid_ip(ip_raw)
            if ip_raw and ip is None:
                issues.append(ImportIssue(excel_row, source_row, "warning", "INVALID_NORMALIZED_IP", ip_raw))
            if not any((name, serial, ip)):
                issues.append(ImportIssue(excel_row, source_row, "error", "NO_DEVICE_IDENTIFIER", "No name, serial, or valid IP"))
                rejected += 1
                continue

            status = _text(get("Review Status"))
            flags = _text(get("Review Issues"))
            if status and status.upper() == "REVIEW":
                issues.append(ImportIssue(excel_row, source_row, "warning", "SOURCE_REVIEW", flags or "Review requested"))
            if not serial:
                issues.append(ImportIssue(excel_row, source_row, "warning", "MISSING_SERIAL", "Accepted as incomplete observation"))

            attributes = {key: get(key) for key in PRESERVED_COLUMNS if key in indexes}
            attributes["source_excel_row"] = source_row
            attributes["source_object_id_scope"] = "export_row_only"
            try:
                devices.append(ImportDevice(
                    source_object_id=source_ref,
                    observation_method="nms",
                    name=name, serial=serial, management_ip=ip,
                    source_attributes=attributes,
                ))
            except ValidationError as exc:
                issues.append(ImportIssue(excel_row, source_row, "error", "SCHEMA_VALIDATION", str(exc)))
                rejected += 1

        dataset = SourceDataset(source_id=source_id, collected_at=collected_at, devices=tuple(devices))
        return ImportResult(dataset=dataset, issues=tuple(issues), total_rows=total_rows, rejected_rows=rejected)
    finally:
        wb.close()
