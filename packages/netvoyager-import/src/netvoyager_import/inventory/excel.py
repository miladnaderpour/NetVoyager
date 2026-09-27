"""Import network devices from an Excel inventory."""

import logging
from dataclasses import dataclass
from ipaddress import IPv4Address
from pathlib import Path
from typing import Any
from types import MappingProxyType
from collections.abc import Mapping

from openpyxl import load_workbook

from netvoyager_network.device.models import NetworkDevice


logger = logging.getLogger("netvoyager.import.inventory.excel")

NAME_COLUMN = "Device Name"
SITE_COLUMN = "Site Ref"
MANAGEMENT_IP_COLUMN = "Management new IP Address"


@dataclass(frozen=True, slots=True)
class InventoryIssue:
    row_number: int
    reason: str


@dataclass(frozen=True, slots=True)
class InventoryReadResult:
    devices: tuple[NetworkDevice, ...]
    issues: tuple[InventoryIssue, ...]
    ip_sites_mapping: Mapping[IPv4Address, frozenset[str]]


def _text(value: Any) -> str | None:
    if value is None:
        return None

    text = str(value).strip()
    return text or None


def _cell(
    row: tuple[Any, ...],
    columns: dict[str, int],
    column_name: str,
) -> Any:
    index = columns.get(column_name)
    if index is None or index >= len(row):
        return None
    return row[index]


def _management_ip(
    value: Any,
    row_number: int,
    issues: list[InventoryIssue],
) -> IPv4Address | None:
    text = _text(value)

    if text is None:
        issues.append(InventoryIssue(row_number, "Missing management IP"))
        return None

    try:
        return IPv4Address(text)
    except ValueError:
        issues.append(InventoryIssue(row_number, "Invalid management IPv4 address"))
        return None


def _device_from_row(
    row: tuple[Any, ...],
    row_number: int,
    columns: dict[str, int],
    issues: list[InventoryIssue],
) -> NetworkDevice | None:
    name = _text(_cell(row, columns, NAME_COLUMN))
    if name is None:
        issues.append(InventoryIssue(row_number, "Missing device name"))
        return None

    site = _text(_cell(row, columns, SITE_COLUMN))
    if site is None:
        issues.append(InventoryIssue(row_number, "Missing site reference"))

    return NetworkDevice(
        name=name,
        role=_text(_cell(row, columns, "Class")),
        site=site,
        management_ip=_management_ip(
            _cell(row, columns, MANAGEMENT_IP_COLUMN),
            row_number,
            issues,
        ),
        host_name=_text(_cell(row, columns, "DNS Domain")),
        manufacturer=_text(_cell(row, columns, "Manufacturer")),
        model=_text(_cell(row, columns, "Model ID")),
        serial_number=_text(_cell(row, columns, "Serial number")),
        status=_text(_cell(row, columns, "Status")),
    )


def read_network_devices(
    path: Path,
    sheet_name: str | None = None,
) -> InventoryReadResult:
    """Read device rows while reporting fields that need investigation."""
    workbook = load_workbook(path, read_only=True, data_only=True)

    try:
        sheet = workbook[sheet_name] if sheet_name else workbook.active

        if sheet is None:
            raise ValueError(
                f"Missing inventory sheet!"
            )
        
        rows = sheet.iter_rows(values_only=True)

        header = next(rows, None)
        if header is None:
            raise ValueError("Inventory sheet is empty")

        columns = {
            text: index
            for index, value in enumerate(header)
            if (text := _text(value)) is not None
        }

        required = {NAME_COLUMN, SITE_COLUMN, MANAGEMENT_IP_COLUMN}
        missing = required - columns.keys()
        if missing:
            raise ValueError(
                f"Missing inventory columns: {', '.join(sorted(missing))}"
            )

        devices: list[NetworkDevice] = []
        issues: list[InventoryIssue] = []
        sites_by_ip: dict[IPv4Address, set[str]] = {}

        for row_number, row in enumerate(rows, start=2):
            if all(_text(value) is None for value in row):
                continue

            device = _device_from_row(row, row_number, columns, issues)
            if device is None:
                continue

            devices.append(device)

            if device.management_ip is None or device.site is None:
                continue

            known_sites = sites_by_ip.setdefault(device.management_ip, set())
            if known_sites and device.site not in known_sites:
                issues.append(
                    InventoryIssue(
                        row_number,
                        "Management IP appears under multiple sites",
                    )
                )
            known_sites.add(device.site)

        result = InventoryReadResult(
            devices=tuple(devices),
            issues=tuple(issues),
            ip_sites_mapping = MappingProxyType(
                {ip: frozenset(sites) for ip, sites in sites_by_ip.items() }
            )
        )

        logger.info(
            "Network device inventory read",
            extra={
                "device_count": len(result.devices),
                "issue_count": len(result.issues),
                "distinct_management_ips": len(sites_by_ip),
            },
        )
        return result
    finally:
        workbook.close()