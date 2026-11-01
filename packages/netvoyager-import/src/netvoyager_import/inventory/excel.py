"""Untrusted spreadsheet inventory -> source-neutral ImportResult.

Preserve every nonempty source row, including duplicate serials/IPs and bad fields.
Inventory labels are NOT device-reported hostnames. No identity decisions here.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime
from ipaddress import ip_address
from pathlib import Path
from typing import Any
from openpyxl import load_workbook
from netvoyager_core.logging import get_logger
from netvoyager_core.exceptions import NetVoyagerError
from netvoyager_schemas.imports import ImportDevice, SourceDataset
from netvoyager_import.contracts import ImportIssue, ImportResult, ImportStatistics

logger = get_logger("import.inventory.excel")
SOURCE_ID = "4sinventory:excel"
REQUIRED_COLUMNS = frozenset({"name", "site", "management_ip"})
PLACEHOLDER_SERIALS = frozenset({"n/a", "na", "none", "null", "unknown", "0", "-"})


class InventoryImportError(NetVoyagerError):
    """Fatal workbook/read/format errors (recoverable rows return issues)."""


def _text(value: Any) -> str | None:
    if value is None:
        return None
    result = str(value).strip()
    return result or None


def _ip(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        return str(ip_address(value))
    except ValueError:
        return None


def read_excel_inventory(
    path: str | Path,
    *,
    collected_at: datetime,
    sheet_name: str | None = None,
    source_id: str = SOURCE_ID,
) -> ImportResult:
    """Read the workbook without dropping or merging rows; collection time is supplied."""
    path = Path(path)
    if collected_at.tzinfo is None or collected_at.utcoffset() is None:
        raise InventoryImportError(code="import.invalid_collection_time", message="collected_at must be timezone-aware")
    try:
        wb = load_workbook(path, read_only=True, data_only=True)
    except (OSError, ValueError, KeyError) as exc:
        raise InventoryImportError(code="import.unreadable_workbook", message="Unable to open Excel inventory", details={"path": str(path)}) from exc
    try:
        if sheet_name is not None and sheet_name not in wb.sheetnames:
            raise InventoryImportError(code="import.missing_sheet", message="Requested Excel worksheet does not exist", details={"sheet": sheet_name})
        sheet = wb[sheet_name] if sheet_name else wb.active
        if sheet is None:
            raise InventoryImportError(code="import.empty_workbook", message="No active worksheet")
        rows = sheet.iter_rows(values_only=True)
        header = next(rows, None)
        if header is None:
            raise InventoryImportError(code="import.empty_sheet", message="Excel worksheet is empty")
        headers = [_text(v) for v in header]
        cols = {name: i for i, name in enumerate(headers) if name}
        missing = sorted(REQUIRED_COLUMNS - cols.keys())
        if missing:
            raise InventoryImportError(code="import.missing_columns", message="Required Excel columns are missing", details={"columns": missing})

        devices: list[ImportDevice] = []
        issues: list[ImportIssue] = []
        serial_rows: dict[str, list[str]] = defaultdict(list)
        ip_rows: dict[str, list[str]] = defaultdict(list)
        total_rows = 0
        def issue(code: str, severity: str, message: str, ref: str) -> None:
            issues.append(ImportIssue(code=code, severity=severity, message=message, source_object_id=ref))

        for number, cells in enumerate(rows, start=2):
            if not any(_text(v) for v in cells):
                continue
            total_rows += 1
            raw = {name: cells[idx] if idx < len(cells) else None for name, idx in cols.items()}
            normalized = {name: _text(value) for name, value in raw.items()}
            ref = f"row:{number}"
            serial = normalized.get("serial_number")
            ip_raw = normalized.get("management_ip")
            parsed_ip = _ip(ip_raw)
            if ip_raw and parsed_ip is None:
                issue("INVALID_MANAGEMENT_IP", "error", "Invalid management IP; raw value retained", ref)
            elif not ip_raw:
                issue("MISSING_MANAGEMENT_IP", "warning", "Missing management IP", ref)
            if serial and serial.casefold() in PLACEHOLDER_SERIALS:
                issue("UNUSABLE_SERIAL", "warning", "Placeholder serial retained as source evidence", ref)
                serial = None
            if not serial:
                issue("MISSING_SERIAL", "warning", "No usable physical serial", ref)
            if not normalized.get("name"):
                issue("MISSING_INVENTORY_NAME", "warning", "Missing inventory label", ref)
            if not normalized.get("site"):
                issue("MISSING_REPORTED_SITE", "warning", "Missing source-reported site", ref)
            # All source values remain evidence. Neither inventory name nor its
            # host_name column is asserted as a device-verified hostname.
            attributes = {name: value for name, value in normalized.items()}
            attributes.update({"source_excel_row": number, "source_object_id_scope": "export_row_only", "inventory_name": normalized.get("name"), "reported_site": normalized.get("site")})
            devices.append(ImportDevice(
                source_object_id=ref,
                observation_method="nms",
                serial=serial,
                name=None,
                management_ip=parsed_ip,
                model=normalized.get("model"),
                manufacturer=normalized.get("manufacturer"),
                source_attributes=attributes,
            ))
            if serial:
                serial_rows[serial.casefold()].append(ref)
            if parsed_ip:
                ip_rows[parsed_ip].append(ref)

        duplicate_serial_groups = 0
        for serial, refs in serial_rows.items():
            if len(refs) > 1:
                duplicate_serial_groups += 1
                issue("DUPLICATE_SERIAL", "warning", f"Serial appears in {len(refs)} inventory rows", refs[0])
        shared_ip_groups = 0
        for ip, refs in ip_rows.items():
            if len(refs) > 1:
                shared_ip_groups += 1
                issue("SHARED_MANAGEMENT_IP", "info", f"Management IP appears in {len(refs)} inventory rows; not necessarily a conflict", refs[0])

        dataset = SourceDataset(source_id=source_id, collected_at=collected_at, devices=tuple(devices))
        stats = ImportStatistics(
            total_rows=total_rows, imported_rows=len(devices), rejected_rows=0,
            warnings=sum(i.severity == "warning" for i in issues),
            errors=sum(i.severity == "error" for i in issues),
            duplicate_serial_groups=duplicate_serial_groups,
            shared_management_ip_groups=shared_ip_groups,
        )
        logger.info("Excel inventory imported", extra={"source_id": source_id, "rows": total_rows, "issues": len(issues)})
        return ImportResult(dataset=dataset, issues=tuple(issues), statistics=stats)
    finally:
        wb.close()


def read_network_devices(path: str | Path, *, collected_at: datetime, sheet_name: str | None = None, source_id: str = SOURCE_ID) -> SourceDataset:
    """Compatibility convenience: retrieve the dataset through the same parser."""
    return read_excel_inventory(path, collected_at=collected_at, sheet_name=sheet_name, source_id=source_id).dataset
