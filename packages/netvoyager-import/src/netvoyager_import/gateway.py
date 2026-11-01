"""One source-typed import entry point; dispatch only, never persist/resolve identity."""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
from netvoyager_core.exceptions import NetVoyagerError
from netvoyager_import.contracts import ImportIssue, ImportResult, ImportStatistics
from netvoyager_import.inventory.excel import read_excel_inventory

class ImportGatewayError(NetVoyagerError):
    """Invalid source selection or unsupported input channel."""


def import_data(
    *,
    source_type: str,
    collected_at: datetime,
    file_path: str | Path | None = None,
    raw_data: str | bytes | None = None,
    sheet_name: str | None = None,
) -> ImportResult:
    """Return a normalized dataset and diagnostic report for a known source."""
    if (file_path is None) == (raw_data is None):
        raise ImportGatewayError(code="import.invalid_input", message="Provide exactly one of file_path and raw_data")
    # V1 supported sources use existing workbook adapters; raw adapters can be
    # registered when implemented, without changing the public signature.
    if raw_data is not None:
        raise ImportGatewayError(code="import.unsupported_raw_input", message="Raw input is not supported by this source adapter yet")
    if source_type == "inventory_excel":
        return read_excel_inventory(file_path, collected_at=collected_at, sheet_name=sheet_name)
    if source_type == "logicmonitor_excel":
        if sheet_name is not None:
            raise ImportGatewayError(code="import.unsupported_sheet_selection", message="LogicMonitor adapter selects its own Inventory sheet")
        from netvoyager_import.sources.logicmonitor.excel import read_logicmonitor_excel
        legacy = read_logicmonitor_excel(file_path, collected_at=collected_at)
        issues = tuple(ImportIssue(code=x.code, severity=x.severity, message=x.message,
                                   source_object_id=f"row:{x.source_excel_row}") for x in legacy.issues)
        stats = ImportStatistics(total_rows=legacy.total_rows, imported_rows=len(legacy.dataset.devices),
                                 rejected_rows=legacy.rejected_rows,
                                 warnings=sum(x.severity == "warning" for x in issues),
                                 errors=sum(x.severity == "error" for x in issues))
        return ImportResult(dataset=legacy.dataset, issues=issues, statistics=stats)
    raise ImportGatewayError(code="import.unknown_source_type", message="Unsupported source type", details={"source_type": source_type})
