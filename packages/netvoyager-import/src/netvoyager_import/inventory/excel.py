"""Import device observations from an Excel inventory."""

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from ipaddress import IPv4Address
from pathlib import Path
from types import MappingProxyType
from typing import Any

from openpyxl import load_workbook


logger = logging.getLogger("netvoyager.import.inventory.excel")

NAME_COLUMN = "name"
HOST_NAME_COLUMN = "host_name"
SITE_COLUMN = "site"
ROLE_COLUMN = "role"

PRIMARY_IPV4_COLUMN = "primary_ipv4"
MANAGEMENT_IP_COLUMN = "management_ip"

MANUFACTURER_COLUMN = "manufacturer"
MODEL_COLUMN = "model"
SERIAL_NUMBER_COLUMN = "serial_number"
ASSET_TAG_COLUMN = "asset_tag"
SOFTWARE_VERSION_COLUMN = "software_version"
STATUS_COLUMN = "status"
VALIDATION_STATUS_COLUMN = "validation_status"


@dataclass(frozen=True, slots=True)
class ExcelDeviceObservation:
    """Device information observed in one Excel inventory row.

    The observation represents source data only. It is not a resolved
    NetworkDevice and has no persistent device identity.

    Missing values are retained as None so analysis can decide whether the
    observation contains enough information to identify or create a device.
    """

    name: str | None = None
    host_name: str | None = None
    site: str | None = None
    role: str | None = None

    primary_IPv4: IPv4Address | None = None
    management_ip: IPv4Address | None = None

    manufacturer: str | None = None
    model: str | None = None
    serial_number: str | None = None
    asset_tag: str | None = None
    software_version: str | None = None
    status: str | None = None

    validation_status: str | None = None

    line_number: int | None = None
    raw_line: str | None = None


@dataclass(frozen=True, slots=True)
class InventoryIssue:
    """Problem detected while reading an inventory row."""

    row_number: int
    reason: str


@dataclass(frozen=True, slots=True)
class InventoryReadResult:
    """Result of reading device observations from an inventory."""

    observations: tuple[ExcelDeviceObservation, ...]
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


def _ipv4(
    value: Any,
    *,
    row_number: int,
    field_name: str,
    issues: list[InventoryIssue],
    required: bool = False,
) -> IPv4Address | None:
    text = _text(value)

    if text is None:
        if required:
            issues.append(
                InventoryIssue(
                    row_number,
                    f"Missing {field_name}",
                )
            )
        return None

    try:
        return IPv4Address(text)
    except ValueError:
        issues.append(
            InventoryIssue(
                row_number,
                f"Invalid {field_name}",
            )
        )
        return None


def _raw_line(
    row: tuple[Any, ...],
    header: tuple[Any, ...],
) -> str:
    values: list[str] = []

    for column_name, value in zip(header, row):
        name = _text(column_name)
        text = _text(value)

        if name is None or text is None:
            continue

        values.append(f"{name}={text}")

    return " | ".join(values)


def _observation_from_row(
    row: tuple[Any, ...],
    *,
    row_number: int,
    header: tuple[Any, ...],
    columns: dict[str, int],
    issues: list[InventoryIssue],
) -> ExcelDeviceObservation:
    name = _text(_cell(row, columns, NAME_COLUMN))
    if name is None:
        issues.append(
            InventoryIssue(
                row_number,
                "Missing device name",
            )
        )

    site = _text(_cell(row, columns, SITE_COLUMN))
    if site is None:
        issues.append(
            InventoryIssue(
                row_number,
                "Missing site",
            )
        )

    management_ip = _ipv4(
        _cell(row, columns, MANAGEMENT_IP_COLUMN),
        row_number=row_number,
        field_name="management IPv4 address",
        issues=issues,
        required=True,
    )

    primary_ipv4 = _ipv4(
        _cell(row, columns, PRIMARY_IPV4_COLUMN),
        row_number=row_number,
        field_name="primary IPv4 address",
        issues=issues,
    )

    return ExcelDeviceObservation(
        name=name,
        host_name=_text(_cell(row, columns, HOST_NAME_COLUMN)),
        site=site,
        role=_text(_cell(row, columns, ROLE_COLUMN)),
        primary_IPv4=primary_ipv4,
        management_ip=management_ip,
        manufacturer=_text(_cell(row, columns, MANUFACTURER_COLUMN)),
        model=_text(_cell(row, columns, MODEL_COLUMN)),
        serial_number=_text(_cell(row, columns, SERIAL_NUMBER_COLUMN)),
        asset_tag=_text(_cell(row, columns, ASSET_TAG_COLUMN)),
        software_version=_text(
            _cell(row, columns, SOFTWARE_VERSION_COLUMN)
        ),
        status=_text(_cell(row, columns, STATUS_COLUMN)),
        line_number=row_number,
        raw_line=_raw_line(row, header),
    )


def read_network_devices(
    path: Path,
    sheet_name: str | None = None,
) -> InventoryReadResult:
    """Read device observations while reporting source-data issues."""
    workbook = load_workbook(path, read_only=True, data_only=True)

    try:
        sheet = workbook[sheet_name] if sheet_name else workbook.active

        if sheet is None:
            raise ValueError("Missing inventory sheet")

        rows = sheet.iter_rows(values_only=True)

        header = next(rows, None)
        if header is None:
            raise ValueError("Inventory sheet is empty")

        columns = {
            text: index
            for index, value in enumerate(header)
            if (text := _text(value)) is not None
        }

        required = {
            NAME_COLUMN,
            SITE_COLUMN,
            MANAGEMENT_IP_COLUMN,
        }
        missing = required - columns.keys()

        if missing:
            raise ValueError(
                f"Missing inventory columns: {', '.join(sorted(missing))}"
            )

        observations: list[ExcelDeviceObservation] = []
        issues: list[InventoryIssue] = []
        sites_by_ip: dict[IPv4Address, set[str]] = {}

        for row_number, row in enumerate(rows, start=2):
            if all(_text(value) is None for value in row):
                continue

            observation = _observation_from_row(
                row,
                row_number=row_number,
                header=header,
                columns=columns,
                issues=issues,
            )
            observations.append(observation)

            if (
                observation.management_ip is None
                or observation.site is None
            ):
                continue

            known_sites = sites_by_ip.setdefault(
                observation.management_ip,
                set(),
            )

            if known_sites and observation.site not in known_sites:
                issues.append(
                    InventoryIssue(
                        row_number,
                        "Management IP appears under multiple sites",
                    )
                )

            known_sites.add(observation.site)

        result = InventoryReadResult(
            observations=tuple(observations),
            issues=tuple(issues),
            ip_sites_mapping=MappingProxyType(
                {
                    ip: frozenset(sites)
                    for ip, sites in sites_by_ip.items()
                }
            ),
        )

        logger.info(
            "Network device inventory read",
            extra={
                "observation_count": len(result.observations),
                "issue_count": len(result.issues),
                "distinct_management_ips": len(sites_by_ip),
            },
        )

        return result
    finally:
        workbook.close()