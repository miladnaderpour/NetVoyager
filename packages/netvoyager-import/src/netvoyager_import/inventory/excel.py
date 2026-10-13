
"""Import device observations from an Excel inventory.

Read inventory rows into source observations without creating NetworkDevice
objects. Validate required values and report source-data inconsistencies.

Duplicate device names can be resolved using deterministic Excel row prefixes.
Duplicate serial numbers are reported according to the selected policy.

Original inventory values are preserved for evidence and troubleshooting.
"""

import logging
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, replace
from ipaddress import IPv4Address
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal, TypeAlias

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


DuplicateNamePolicy: TypeAlias = Literal[
    "prefix",
    "warn",
    "error",
    "ignore",
]

DuplicateSerialPolicy: TypeAlias = Literal[
    "warn",
    "error",
    "ignore",
]


UNKNOWN_SERIAL_VALUES = frozenset({
    "n/a",
    "na",
    "none",
    "null",
    "unknown",
    "0",
    "-",
})


@dataclass(frozen=True, slots=True)
class ExcelDeviceObservation:
    """Device information observed in one Excel inventory row.

    The observation represents imported source data rather than a resolved
    NetworkDevice. It does not contain a persistent device identity.

    The name may be modified by the configured duplicate-name policy to
    provide a unique imported name. The original name remains available
    in raw_line.

    Missing values are preserved as None so downstream analysis can decide
    whether an observation is sufficient to create a device.
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
    """An issue detected while reading an Excel inventory row."""

    row_number: int
    reason: str


@dataclass(frozen=True, slots=True)
class InventoryReadResult:
    """Inventory observations, validation issues, and management IP mappings.

    Observations preserve source row order and are never merged.

    The IP-to-site mapping contains every site associated with each
    management address, including addresses shared by multiple devices.
    """

    observations: tuple[ExcelDeviceObservation, ...]
    issues: tuple[InventoryIssue, ...]
    ip_sites_mapping: Mapping[IPv4Address, frozenset[str]]


def _text(value: Any) -> str | None:
    """Convert a source value to stripped text or None."""
    if value is None:
        return None

    text = str(value).strip()
    return text or None


def _cell(
    row: tuple[Any, ...],
    columns: dict[str, int],
    column_name: str,
) -> Any:
    """Return a column value or None when the column is unavailable."""
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
    """Parse an IPv4 address and report missing or invalid values."""
    text = _text(value)

    if text is None:
        if required:
            issues.append(
                InventoryIssue(
                    row_number=row_number,
                    reason=f"Missing {field_name}",
                )
            )

        return None

    try:
        return IPv4Address(text)
    except ValueError:
        issues.append(
            InventoryIssue(
                row_number=row_number,
                reason=f"Invalid {field_name}",
            )
        )

        return None


def _raw_line(
    row: tuple[Any, ...],
    header: tuple[Any, ...],
) -> str:
    """Serialize populated source cells for evidence and troubleshooting."""
    values: list[str] = []

    for column_name, value in zip(header, row):
        name = _text(column_name)
        text = _text(value)

        if name is None or text is None:
            continue

        values.append(f"{name}={text}")

    return " | ".join(values)


def _duplicate_key(value: str | None) -> str | None:
    """Normalize a value for case-insensitive duplicate detection.

    Surrounding whitespace is ignored. Missing and whitespace-only
    values do not participate in duplicate detection.
    """
    if value is None:
        return None

    return value.strip().casefold() or None


def _serial_key(value: str | None) -> str | None:
    """Return a normalized serial number excluding known placeholders.

    Serial numbers are compared case-insensitively without changing
    their original values in imported observations.
    """
    key = _duplicate_key(value)

    if key is None or key in UNKNOWN_SERIAL_VALUES:
        return None

    return key


def _resolve_duplicate_observations(
    observations: list[ExcelDeviceObservation],
    issues: list[InventoryIssue],
    *,
    duplicate_name_policy: DuplicateNamePolicy,
    duplicate_serial_policy: DuplicateSerialPolicy,
) -> list[ExcelDeviceObservation]:
    """Apply duplicate-name and duplicate-serial policies.

    Duplicate names are identified across the complete inventory using
    case-insensitive comparison.

    Under the prefix policy, every occurrence of a duplicated name
    receives the deterministic format DUP-{row_number}-{original_name}.

    Generated names are checked against original inventory names and
    previously generated names. Numeric suffixes resolve any collisions.

    Duplicate serial numbers are reported or rejected according to the
    selected policy. They never cause records to be renamed or merged.

    Original source values remain available in raw_line.
    """
    name_counts = Counter(
        key
        for observation in observations
        if (key := _duplicate_key(observation.name)) is not None
    )

    serial_counts = Counter(
        key
        for observation in observations
        if (key := _serial_key(observation.serial_number)) is not None
    )

    reserved_names: set[str] = {
        key
        for observation in observations
        if (key := _duplicate_key(observation.name)) is not None
    }

    resolved_observations: list[ExcelDeviceObservation] = []

    for observation in observations:
        row_number = observation.line_number

        if row_number is None:
            raise ValueError(
                "Excel observation is missing its source row number"
            )

        name_key = _duplicate_key(observation.name)
        serial_key = _serial_key(observation.serial_number)

        resolved = observation

        if name_key is not None and name_counts[name_key] > 1:
            if duplicate_name_policy == "error":
                raise ValueError(
                    f"Duplicate device name at row {row_number}: "
                    f"{observation.name}"
                )

            if duplicate_name_policy in {"prefix", "warn"}:
                issues.append(
                    InventoryIssue(
                        row_number=row_number,
                        reason=(
                            f"Duplicate device name: {observation.name}"
                        ),
                    )
                )

            if duplicate_name_policy == "prefix":
                candidate = f"DUP-{row_number}-{observation.name}"
                generated_name = candidate
                suffix = 2

                while generated_name.strip().casefold() in reserved_names:
                    generated_name = f"{candidate}-{suffix}"
                    suffix += 1

                reserved_names.add(
                    generated_name.strip().casefold()
                )

                resolved = replace(
                    observation,
                    name=generated_name,
                )

        if serial_key is not None and serial_counts[serial_key] > 1:
            if duplicate_serial_policy == "error":
                raise ValueError(
                    f"Duplicate serial number at row {row_number}: "
                    f"{observation.serial_number}"
                )

            if duplicate_serial_policy == "warn":
                issues.append(
                    InventoryIssue(
                        row_number=row_number,
                        reason=(
                            "Duplicate serial number: "
                            f"{observation.serial_number}"
                        ),
                    )
                )

        resolved_observations.append(resolved)

    return resolved_observations


def _observation_from_row(
    row: tuple[Any, ...],
    *,
    row_number: int,
    header: tuple[Any, ...],
    columns: dict[str, int],
    issues: list[InventoryIssue],
) -> ExcelDeviceObservation:
    """Create one device observation from an Excel inventory row.

    Missing required values and invalid IPv4 addresses are reported
    without discarding the source observation.
    """
    name = _text(_cell(row, columns, NAME_COLUMN))

    if name is None:
        issues.append(
            InventoryIssue(
                row_number=row_number,
                reason="Missing device name",
            )
        )

    site = _text(_cell(row, columns, SITE_COLUMN))

    if site is None:
        issues.append(
            InventoryIssue(
                row_number=row_number,
                reason="Missing site",
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
        validation_status=_text(
            _cell(row, columns, VALIDATION_STATUS_COLUMN)
        ),
        line_number=row_number,
        raw_line=_raw_line(row, header),
    )


def read_network_devices(
    path: Path,
    sheet_name: str | None = None,
    *,
    duplicate_name_policy: DuplicateNamePolicy = "prefix",
    duplicate_serial_policy: DuplicateSerialPolicy = "warn",
) -> InventoryReadResult:
    """Read device observations with configurable duplicate handling.

    Parse the inventory while preserving source row order and reporting
    missing values, invalid addresses, and conflicting management IP sites.

    Duplicate-name policies:
        prefix: Report duplicates and generate unique DUP-row-name values.
        warn:   Report duplicates without modifying names.
        error:  Raise ValueError on a duplicate name.
        ignore: Preserve names without duplicate-name issues.

    Duplicate-serial policies:
        warn:   Report duplicate non-placeholder serial numbers.
        error:  Raise ValueError on duplicate serial numbers.
        ignore: Preserve serial numbers without duplicate-serial issues.

    Duplicate checks are case-insensitive. Empty names and known serial
    placeholders are excluded from their respective duplicate checks.

    The original source values remain available in raw_line. Observations
    are never merged or discarded because of duplicate values.

    Raise ValueError for invalid policies, missing required columns,
    missing inventory sheets, or empty workbooks.
    """
    if duplicate_name_policy not in {
        "prefix",
        "warn",
        "error",
        "ignore",
    }:
        raise ValueError(
            f"Invalid duplicate name policy: {duplicate_name_policy}"
        )

    if duplicate_serial_policy not in {
        "warn",
        "error",
        "ignore",
    }:
        raise ValueError(
            f"Invalid duplicate serial policy: {duplicate_serial_policy}"
        )

    workbook = load_workbook(
        path,
        read_only=True,
        data_only=True,
    )

    try:
        sheet = (
            workbook[sheet_name]
            if sheet_name is not None
            else workbook.active
        )

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
                "Missing inventory columns: "
                f"{', '.join(sorted(missing))}"
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
                        row_number=row_number,
                        reason=(
                            "Management IP appears under multiple sites"
                        ),
                    )
                )

            known_sites.add(observation.site)

        observations = _resolve_duplicate_observations(
            observations,
            issues,
            duplicate_name_policy=duplicate_name_policy,
            duplicate_serial_policy=duplicate_serial_policy,
        )

        result = InventoryReadResult(
            observations=tuple(observations),
            issues=tuple(issues),
            ip_sites_mapping=MappingProxyType({
                ip: frozenset(sites)
                for ip, sites in sites_by_ip.items()
            }),
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
