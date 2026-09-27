"""Parse JSON exports produced by the Panorama inventory collector."""

import json
import logging
from datetime import datetime, timezone
from ipaddress import IPv4Address, IPv4Interface, IPv4Network
from typing import Any, cast
from xml.etree import ElementTree

from .models import (
    CollectionFailure,
    CollectionState,
    CollectionStatus,
    FirewallInventory,
    HAInfo,
    InterfaceAddress,
    IssueSeverity,
    ManagementInfo,
    PanoramaImportIssue,
    PanoramaInventoryResult,
    StaticRoute,
)
from .routing_parser import parse_virtual_routers


logger = logging.getLogger("netvoyager.paloalto.inventory.parser")

SUPPORTED_VERSIONS = {"2.0", "2.1"}
COLLECTION_STATES = {"pending", "success", "partial", "failed"}
UNAVAILABLE_VALUES = {"", "unknown", "n/a", "none"}


def _object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def _array(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{path}: expected a JSON array")
    return value


def _required_text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path}: expected a nonempty string")
    return value.strip()


def _count(value: Any, path: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{path}: expected a nonnegative integer")
    return value


def _timestamp(value: Any, path: str) -> datetime:
    text = _required_text(value, path)

    try:
        result = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{path}: invalid timestamp") from exc

    if result.utcoffset() is None:
        raise ValueError(f"{path}: timestamp must include a timezone")

    return result.astimezone(timezone.utc)


class _Parser:
    def __init__(self, schema_version: str) -> None:
        self.schema_version = schema_version
        self.issues: list[PanoramaImportIssue] = []
        self.serial: str | None = None

    def issue(
        self,
        path: str,
        reason: str,
        value: Any = None,
        severity: IssueSeverity = "warning",
    ) -> None:
        self.issues.append(
            PanoramaImportIssue(
                severity=severity,
                path=path,
                reason=reason,
                firewall_serial=self.serial,
                raw_value_json=json.dumps(value, ensure_ascii=False),
            )
        )

    def text(self, value: Any, path: str) -> str | None:
        if value is None or isinstance(value, str):
            return value

        self.issue(path, "Expected a string or null", value)
        return None

    def boolean(self, value: Any, path: str) -> bool | None:
        if value is None or type(value) is bool:
            return value

        self.issue(path, "Expected a boolean or null", value)
        return None

    def address(
        self,
        value: str | None,
        path: str,
    ) -> IPv4Address | None:
        if value is None or value.strip().lower() in UNAVAILABLE_VALUES:
            self.issue(path, "IPv4 address unavailable", value)
            return None

        try:
            return IPv4Address(value.strip())
        except ValueError:
            self.issue(path, "Invalid IPv4 address", value)
            return None

    def optional_timestamp(
        self,
        value: Any,
        path: str,
    ) -> datetime | None:
        if value is None:
            return None

        try:
            return _timestamp(value, path)
        except ValueError as exc:
            self.issue(path, str(exc), value)
            return None

    def network(
        self,
        value: str | None,
        path: str,
    ) -> IPv4Network | None:
        # Do not let a bare address implicitly become a /32.
        if value is None or "/" not in value:
            self.issue(
                path,
                "IPv4 network requires an explicit mask",
                value,
            )
            return None

        try:
            return IPv4Network(value.strip(), strict=False)
        except ValueError:
            self.issue(path, "Invalid IPv4 network", value)
            return None

    def check_reported_prefix(
        self,
        reported: str | None,
        calculated: IPv4Network | None,
        path: str,
    ) -> None:
        if reported is None:
            return

        parsed = self.network(reported, path)

        if (
            parsed is not None
            and calculated is not None
            and parsed != calculated
        ):
            self.issue(
                path,
                f"Reported prefix differs from calculated network {calculated}",
                reported,
            )

    def management(
        self,
        value: Any,
        path: str,
    ) -> ManagementInfo | None:
        if value is None:
            return None

        data = _object(value, path)

        raw_ip = self.text(
            data.get("ip_address"), f"{path}.ip_address"
        )
        raw_mask = self.text(
            data.get("netmask"), f"{path}.netmask"
        )
        raw_gateway = self.text(
            data.get("default_gateway"), f"{path}.default_gateway"
        )

        address = self.address(raw_ip, f"{path}.ip_address")
        gateway = self.address(
            raw_gateway, f"{path}.default_gateway"
        )
        prefix_length = None

        if (
            raw_mask is None
            or raw_mask.strip().lower() in UNAVAILABLE_VALUES
        ):
            self.issue(
                f"{path}.netmask",
                "Management netmask unavailable",
                raw_mask,
            )
        else:
            try:
                mask = raw_mask.strip()
                network = IPv4Network(f"0.0.0.0/{mask}")

                if str(network.netmask) != mask:
                    raise ValueError("Not a dotted subnet mask")

                prefix_length = network.prefixlen
            except ValueError:
                self.issue(
                    f"{path}.netmask",
                    "Invalid management netmask",
                    raw_mask,
                )

        return ManagementInfo(
            ip_address=address,
            prefix_length=prefix_length,
            default_gateway=gateway,
            is_dhcp=self.boolean(
                data.get("is_dhcp"), f"{path}.is_dhcp"
            ),
            raw_ip_address=raw_ip,
            raw_netmask=raw_mask,
            raw_default_gateway=raw_gateway,
            collected_at_utc=self.optional_timestamp(
                data.get("collected_at_utc"),
                f"{path}.collected_at_utc",
            ),
        )

    def ha(self, value: Any, path: str) -> HAInfo | None:
        if value is None:
            return None

        data = _object(value, path)

        peer_serial = self.text(
            data.get("peer_serial"), f"{path}.peer_serial"
        )
        peer_serial = (
            peer_serial.strip() or None
            if peer_serial is not None
            else None
        )
        raw_xml = self.text(
            data.get("raw_xml"), f"{path}.raw_xml"
        )

        # Recover the serial missed by the original v2 collector.
        if peer_serial is None and raw_xml:
            try:
                upper = raw_xml.upper()

                if "<!DOCTYPE" in upper or "<!ENTITY" in upper:
                    raise ValueError(
                        "DTD/entity declarations are not supported"
                    )

                root = ElementTree.fromstring(raw_xml)

                if root.tag == "response":
                    result = root.find("result")
                elif root.tag == "result":
                    result = root
                else:
                    result = None

                if result is None:
                    raise ValueError("Expected an HA result element")

                recovered = result.findtext(
                    "group/peer-info/serial-num"
                )

                if recovered and recovered.strip():
                    peer_serial = recovered.strip()

                    self.issue(
                        f"{path}.peer_serial",
                        "Recovered peer serial from HA raw XML",
                        peer_serial,
                        severity="info",
                    )
            except (ElementTree.ParseError, ValueError) as exc:
                self.issue(
                    f"{path}.raw_xml",
                    f"Could not read HA fallback XML: {exc}",
                    raw_xml,
                )

        return HAInfo(
            enabled=self.boolean(
                data.get("enabled"), f"{path}.enabled"
            ),
            mode=self.text(data.get("mode"), f"{path}.mode"),
            group_id=self.text(
                data.get("group_id"), f"{path}.group_id"
            ),
            local_state=self.text(
                data.get("local_state"), f"{path}.local_state"
            ),
            peer_serial=peer_serial,
            peer_state=self.text(
                data.get("peer_state"), f"{path}.peer_state"
            ),
            peer_connection=self.text(
                data.get("peer_connection"), f"{path}.peer_connection"
            ),
            config_sync=self.text(
                data.get("config_sync"), f"{path}.config_sync"
            ),
            sync_enabled=self.boolean(
                data.get("sync_enabled"), f"{path}.sync_enabled"
            ),
            collected_at_utc=self.optional_timestamp(
                data.get("collected_at_utc"),
                f"{path}.collected_at_utc",
            ),
            raw_xml=raw_xml,
        )

    def interface_address(
        self,
        data: dict[str, Any],
        path: str,
        index: int,
    ) -> InterfaceAddress:
        interface = _required_text(
            data.get("interface"), f"{path}.interface"
        )
        router = _required_text(
            data.get("virtual_router"), f"{path}.virtual_router"
        )

        raw = data.get("configured_value")
        text = _required_text(raw, f"{path}.configured_value")
        reported = self.text(
            data.get("prefix"), f"{path}.prefix"
        )

        address = None
        prefix_length = None

        if "/" in text:
            try:
                parsed = IPv4Interface(text)
                address = parsed.ip
                prefix_length = parsed.network.prefixlen
            except ValueError:
                self.issue(
                    f"{path}.configured_value",
                    "Invalid configured IPv4 interface address",
                    raw,
                )

                # Retain a valid host address even if its mask is invalid.
                host_text = text.split("/", 1)[0]

                try:
                    address = IPv4Address(host_text)
                except ValueError:
                    pass
        else:
            address = self.address(
                text, f"{path}.configured_value"
            )

            if address is not None:
                if interface.lower().startswith("loopback."):
                    prefix_length = 32
                else:
                    self.issue(
                        f"{path}.configured_value",
                        "Interface address has no mask; prefix length remains unknown",
                        raw,
                    )

        record = InterfaceAddress(
            interface=interface,
            virtual_router=router,
            ip_address=address,
            prefix_length=prefix_length,
            configured_value=raw,
            reported_prefix=reported,
            record_index=index,
        )

        self.check_reported_prefix(
            reported, record.network, f"{path}.prefix"
        )
        return record

    def static_route(
        self,
        data: dict[str, Any],
        path: str,
        index: int,
    ) -> StaticRoute:
        router = _required_text(
            data.get("virtual_router"), f"{path}.virtual_router"
        )
        raw = data.get("configured_value")
        _required_text(raw, f"{path}.configured_value")

        destination = self.network(
            raw, f"{path}.configured_value"
        )
        reported = self.text(
            data.get("prefix"), f"{path}.prefix"
        )

        self.check_reported_prefix(
            reported, destination, f"{path}.prefix"
        )

        return StaticRoute(
            virtual_router=router,
            route_name=self.text(
                data.get("route_name"), f"{path}.route_name"
            ),
            destination=destination,
            interface=self.text(
                data.get("interface"), f"{path}.interface"
            ),
            next_hop=self.text(
                data.get("next_hop"), f"{path}.next_hop"
            ),
            configured_value=raw,
            reported_prefix=reported,
            record_index=index,
        )

    def collection_status(
        self,
        value: Any,
        path: str,
    ) -> CollectionStatus:
        data = _object(value, path)
        states: dict[str, CollectionState | None] = {}

        sections = ["subnets", "management", "ha"]

        if self.schema_version == "2.1":
            sections.append("virtual_routers")

        for section in sections:
            state = data.get(section)

            if (
                not isinstance(state, str)
                or state not in COLLECTION_STATES
            ):
                self.issue(
                    f"{path}.{section}",
                    "Missing or unrecognized collection status",
                    state,
                )
                states[section] = None
            else:
                states[section] = cast(CollectionState, state)

        return CollectionStatus(
            subnets=states["subnets"],
            management=states["management"],
            ha=states["ha"],
            virtual_routers=states.get("virtual_routers"),
        )

    def firewall(
        self,
        value: Any,
        path: str,
    ) -> FirewallInventory:
        data = _object(value, path)
        serial = _required_text(
            data.get("serial"), f"{path}.serial"
        )
        self.serial = serial

        hostname = _required_text(
            data.get("hostname"), f"{path}.hostname"
        )

        try:
            status = self.collection_status(
                data.get("collection_status"),
                f"{path}.collection_status",
            )
        except ValueError as exc:
            self.issue(
                f"{path}.collection_status",
                str(exc),
                data.get("collection_status"),
                severity="error",
            )
            status = CollectionStatus(
                subnets=None,
                management=None,
                ha=None,
                virtual_routers=None,
            )

        management = None
        ha = None

        try:
            management = self.management(
                data.get("management"), f"{path}.management"
            )
        except ValueError as exc:
            self.issue(
                f"{path}.management",
                str(exc),
                data.get("management"),
                severity="error",
            )

        try:
            ha = self.ha(data.get("ha"), f"{path}.ha")
        except ValueError as exc:
            self.issue(
                f"{path}.ha",
                str(exc),
                data.get("ha"),
                severity="error",
            )

        if management is None and status.management == "success":
            self.issue(
                f"{path}.management",
                "Management unavailable despite collector reporting success",
                data.get("management"),
            )

        if ha is None and status.ha == "success":
            self.issue(
                f"{path}.ha",
                "HA unavailable despite collector reporting success",
                data.get("ha"),
            )

        interfaces: list[InterfaceAddress] = []
        routes: list[StaticRoute] = []

        raw_records = data.get("subnets")

        if not isinstance(raw_records, list):
            self.issue(
                f"{path}.subnets",
                "Subnet collection is missing or is not an array",
                raw_records,
                severity="error",
            )
            records = []
        else:
            records = raw_records

        for index, value in enumerate(records):
            record_path = f"{path}.subnets[{index}]"

            try:
                record = _object(value, record_path)
                source = record.get("source")

                if source == "connected":
                    interfaces.append(
                        self.interface_address(
                            record, record_path, index
                        )
                    )
                elif source == "static":
                    routes.append(
                        self.static_route(
                            record, record_path, index
                        )
                    )
                else:
                    raise ValueError(
                        f"{record_path}: unrecognized source"
                    )
            except ValueError as exc:
                self.issue(
                    record_path,
                    str(exc),
                    value,
                    severity="error",
                )

        virtual_routers = None

        if self.schema_version == "2.1":
            virtual_routers, routing_issues = parse_virtual_routers(
                value=data.get("virtual_routers"),
                firewall_serial=serial,
                path=f"{path}.virtual_routers",
            )
            self.issues.extend(routing_issues)

            if (
                virtual_routers is None
                and status.virtual_routers == "success"
            ):
                self.issue(
                    f"{path}.virtual_routers",
                    "Virtual routers unavailable despite collector reporting success",
                    data.get("virtual_routers"),
                )

        return FirewallInventory(
            serial=serial,
            hostname=hostname,
            management=management,
            ha=ha,
            interface_addresses=tuple(interfaces),
            static_routes=tuple(routes),
            collection_status=status,
            virtual_routers=virtual_routers,
        )


def parse_panorama_inventory(
    raw_text: str,
) -> PanoramaInventoryResult:
    """Parse a schema 2.0 or 2.1 export.

    Invalid JSON or an incompatible report structure raises ValueError.
    Record-level problems are retained as parsing issues.
    Valid records, duplicates, and original values are preserved.
    """
    data = _object(
        json.loads(raw_text.lstrip("\ufeff")),
        "$",
    )

    version = _required_text(
        data.get("schema_version"), "$.schema_version"
    )

    if version not in SUPPORTED_VERSIONS:
        raise ValueError(
            f"Unsupported Panorama schema version: {version}"
        )

    panorama = _required_text(
        data.get("panorama"), "$.panorama"
    )
    started = _timestamp(
        data.get("collection_started_at_utc"),
        "$.collection_started_at_utc",
    )
    collected = _timestamp(
        data.get("collected_at_utc"),
        "$.collected_at_utc",
    )
    connected_count = _count(
        data.get("panorama_connected"),
        "$.panorama_connected",
    )
    selected_count = _count(
        data.get("selected_connected"),
        "$.selected_connected",
    )

    not_connected = tuple(
        _required_text(
            value,
            f"$.selected_not_connected[{index}]",
        )
        for index, value in enumerate(
            _array(
                data.get("selected_not_connected"),
                "$.selected_not_connected",
            )
        )
    )

    parser = _Parser(schema_version=version)
    firewalls: list[FirewallInventory] = []
    seen_serials: set[str] = set()

    raw_firewalls = _array(
        data.get("firewalls"), "$.firewalls"
    )

    for index, value in enumerate(raw_firewalls):
        path = f"$.firewalls[{index}]"
        parser.serial = None

        try:
            firewall = parser.firewall(value, path)
        except ValueError as exc:
            parser.issue(
                path,
                str(exc),
                value,
                severity="error",
            )
            continue

        if firewall.serial in seen_serials:
            parser.issue(
                f"{path}.serial",
                "Duplicate firewall serial; both records retained",
                firewall.serial,
            )

        seen_serials.add(firewall.serial)
        firewalls.append(firewall)

    parser.serial = None
    failures: list[CollectionFailure] = []

    raw_failures = _array(
        data.get("failures"), "$.failures"
    )

    for index, value in enumerate(raw_failures):
        path = f"$.failures[{index}]"

        try:
            failure = _object(value, path)

            failures.append(
                CollectionFailure(
                    serial=_required_text(
                        failure.get("serial"),
                        f"{path}.serial",
                    ),
                    hostname=parser.text(
                        failure.get("hostname"),
                        f"{path}.hostname",
                    ),
                    section=_required_text(
                        failure.get("section"),
                        f"{path}.section",
                    ),
                    error=_required_text(
                        failure.get("error"),
                        f"{path}.error",
                    ),
                )
            )
        except ValueError as exc:
            parser.issue(
                path,
                str(exc),
                value,
                severity="error",
            )

    if len(raw_firewalls) != selected_count:
        parser.issue(
            "$.selected_connected",
            f"Reported count differs from {len(raw_firewalls)} firewall records",
            selected_count,
        )

    if collected < started:
        parser.issue(
            "$.collected_at_utc",
            "Collection finished before its reported start time",
            data.get("collected_at_utc"),
        )

    result = PanoramaInventoryResult(
        schema_version=version,
        panorama=panorama,
        collection_started_at_utc=started,
        collected_at_utc=collected,
        panorama_connected=connected_count,
        selected_connected=selected_count,
        selected_not_connected=not_connected,
        firewalls=tuple(firewalls),
        collection_failures=tuple(failures),
        issues=tuple(parser.issues),
    )

    logger.info(
        "Panorama inventory parsed",
        extra={
            "schema_version": result.schema_version,
            "firewall_count": len(result.firewalls),
            "interface_address_count": sum(
                len(f.interface_addresses)
                for f in result.firewalls
            ),
            "static_route_count": sum(
                len(f.static_routes)
                for f in result.firewalls
            ),
            "virtual_router_count": sum(
                len(f.virtual_routers or ())
                for f in result.firewalls
            ),
            "collection_failure_count": len(
                result.collection_failures
            ),
            "issue_count": len(result.issues),
        },
    )

    return result