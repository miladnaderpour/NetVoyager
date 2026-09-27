"""Parse virtual-router and BGP configuration from collector JSON."""

import json
from collections.abc import Callable
from ipaddress import IPv4Address
from typing import Any, TypeVar
from xml.etree import ElementTree

from .models import (
    BgpConfiguration,
    BgpPeer,
    BgpPeerGroup,
    BgpRule,
    IssueSeverity,
    PanoramaImportIssue,
    RedistributionProfile,
    VirtualRouterConfiguration,
)


T = TypeVar("T")


class _RoutingParser:
    def __init__(self, firewall_serial: str) -> None:
        self.firewall_serial = firewall_serial
        self.issues: list[PanoramaImportIssue] = []

    def issue(
        self,
        path: str,
        reason: str,
        value: Any,
        severity: IssueSeverity = "warning",
    ) -> None:
        self.issues.append(
            PanoramaImportIssue(
                severity=severity,
                path=path,
                reason=reason,
                firewall_serial=self.firewall_serial,
                raw_value_json=json.dumps(value, ensure_ascii=False),
            )
        )

    @staticmethod
    def object(value: Any, path: str) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ValueError(f"{path}: expected a JSON object")
        return value

    @staticmethod
    def name(value: Any, path: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{path}: expected a nonempty string")
        return value.strip()

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

    def items(
        self,
        value: Any,
        path: str,
        reader: Callable[[Any, str], T],
    ) -> tuple[T, ...]:
        if not isinstance(value, list):
            self.issue(
                path,
                "Expected an array; collection is unavailable",
                value,
                severity="error",
            )
            return ()

        result: list[T] = []

        for index, item in enumerate(value):
            item_path = f"{path}[{index}]"

            try:
                result.append(reader(item, item_path))
            except ValueError as exc:
                self.issue(
                    item_path,
                    str(exc),
                    item,
                    severity="error",
                )

        return tuple(result)

    def asn(self, value: str | None, path: str) -> int | None:
        if value is None:
            return None

        text = value.strip()

        try:
            if "." in text:
                parts = text.split(".")

                if len(parts) != 2:
                    raise ValueError

                if not all(
                    part.isascii() and part.isdigit()
                    for part in parts
                ):
                    raise ValueError

                high, low = map(int, parts)

                if not (0 <= high <= 65535 and 0 <= low <= 65535):
                    raise ValueError

                result = high * 65536 + low
            else:
                if not text.isascii() or not text.isdigit():
                    raise ValueError

                result = int(text)

            if not 1 <= result <= 4294967295:
                raise ValueError

            return result
        except ValueError:
            self.issue(
                path,
                "Invalid or unresolved configured ASN",
                value,
            )
            return None

    def router_id(
        self,
        value: str | None,
        path: str,
    ) -> IPv4Address | None:
        if value is None:
            return None

        try:
            return IPv4Address(value.strip())
        except ValueError:
            self.issue(
                path,
                "Invalid or unresolved BGP router ID",
                value,
            )
            return None

    def xml(self, value: Any, path: str) -> str | None:
        raw = self.text(value, path)

        if raw is None:
            return None

        try:
            upper = raw.upper()

            if "<!DOCTYPE" in upper or "<!ENTITY" in upper:
                raise ValueError(
                    "DTD/entity declarations are not supported"
                )

            ElementTree.fromstring(raw)
        except (ElementTree.ParseError, ValueError) as exc:
            self.issue(
                path,
                f"Invalid XML retained for investigation: {exc}",
                raw,
            )

        return raw

    def peer(self, value: Any, path: str) -> BgpPeer:
        data = self.object(value, path)
        raw_as = self.text(data.get("peer_as"), f"{path}.peer_as")

        return BgpPeer(
            name=self.name(data.get("name"), f"{path}.name"),
            enabled=self.boolean(
                data.get("enabled"), f"{path}.enabled"
            ),
            peer_as=self.asn(raw_as, f"{path}.peer_as"),
            raw_peer_as=raw_as,
            peer_address_ip=self.text(
                data.get("peer_address_ip"),
                f"{path}.peer_address_ip",
            ),
            peer_address_fqdn=self.text(
                data.get("peer_address_fqdn"),
                f"{path}.peer_address_fqdn",
            ),
            local_interface=self.text(
                data.get("local_interface"),
                f"{path}.local_interface",
            ),
            local_address=self.text(
                data.get("local_address"),
                f"{path}.local_address",
            ),
            address_family=self.text(
                data.get("address_family"),
                f"{path}.address_family",
            ),
            enable_mp_bgp=self.boolean(
                data.get("enable_mp_bgp"),
                f"{path}.enable_mp_bgp",
            ),
            raw_xml=self.xml(
                data.get("raw_xml"), f"{path}.raw_xml"
            ),
        )

    def peer_group(self, value: Any, path: str) -> BgpPeerGroup:
        data = self.object(value, path)

        return BgpPeerGroup(
            name=self.name(data.get("name"), f"{path}.name"),
            enabled=self.boolean(
                data.get("enabled"), f"{path}.enabled"
            ),
            type=self.text(data.get("type"), f"{path}.type"),
            peers=self.items(
                data.get("peers"),
                f"{path}.peers",
                self.peer,
            ),
            raw_xml=self.xml(
                data.get("raw_xml"), f"{path}.raw_xml"
            ),
        )

    def rule(self, value: Any, path: str) -> BgpRule:
        data = self.object(value, path)

        return BgpRule(
            name=self.name(data.get("name"), f"{path}.name"),
            enabled=self.boolean(
                data.get("enabled"), f"{path}.enabled"
            ),
            raw_xml=self.xml(
                data.get("raw_xml"), f"{path}.raw_xml"
            ),
        )

    def profile(
        self,
        value: Any,
        path: str,
    ) -> RedistributionProfile:
        data = self.object(value, path)

        return RedistributionProfile(
            name=self.name(data.get("name"), f"{path}.name"),
            raw_xml=self.xml(
                data.get("raw_xml"), f"{path}.raw_xml"
            ),
        )

    def bgp(self, value: Any, path: str) -> BgpConfiguration:
        data = self.object(value, path)

        raw_as = self.text(
            data.get("local_as"), f"{path}.local_as"
        )
        raw_id = self.text(
            data.get("router_id"), f"{path}.router_id"
        )

        result = BgpConfiguration(
            present=self.boolean(
                data.get("present"), f"{path}.present"
            ),
            enabled=self.boolean(
                data.get("enabled"), f"{path}.enabled"
            ),
            local_as=self.asn(raw_as, f"{path}.local_as"),
            raw_local_as=raw_as,
            router_id=self.router_id(raw_id, f"{path}.router_id"),
            raw_router_id=raw_id,
            install_route=self.boolean(
                data.get("install_route"),
                f"{path}.install_route",
            ),
            reject_default_route=self.boolean(
                data.get("reject_default_route"),
                f"{path}.reject_default_route",
            ),
            allow_redistribute_default_route=self.boolean(
                data.get("allow_redistribute_default_route"),
                f"{path}.allow_redistribute_default_route",
            ),
            peer_groups=self.items(
                data.get("peer_groups"),
                f"{path}.peer_groups",
                self.peer_group,
            ),
            import_rules=self.items(
                data.get("import_rules"),
                f"{path}.import_rules",
                self.rule,
            ),
            export_rules=self.items(
                data.get("export_rules"),
                f"{path}.export_rules",
                self.rule,
            ),
            redistribution_rules=self.items(
                data.get("redistribution_rules"),
                f"{path}.redistribution_rules",
                self.rule,
            ),
            raw_xml=self.xml(
                data.get("raw_xml"), f"{path}.raw_xml"
            ),
        )

        if result.enabled is True:
            if result.local_as is None:
                self.issue(
                    f"{path}.local_as",
                    "Enabled BGP instance has no usable local ASN",
                    raw_as,
                )

            if result.router_id is None:
                self.issue(
                    f"{path}.router_id",
                    "Enabled BGP instance has no usable router ID",
                    raw_id,
                )

        if result.present is False and result.enabled is True:
            self.issue(
                path,
                "BGP is marked absent but enabled",
                value,
            )

        return result

    def virtual_router(
        self,
        value: Any,
        path: str,
    ) -> VirtualRouterConfiguration:
        data = self.object(value, path)
        name = self.name(data.get("name"), f"{path}.name")

        bgp = None

        try:
            bgp = self.bgp(data.get("bgp"), f"{path}.bgp")
        except ValueError as exc:
            self.issue(
                f"{path}.bgp",
                str(exc),
                data.get("bgp"),
                severity="error",
            )

        return VirtualRouterConfiguration(
            name=name,
            interfaces=self.items(
                data.get("interfaces"),
                f"{path}.interfaces",
                self.name,
            ),
            bgp=bgp,
            redistribution_profiles=self.items(
                data.get("redistribution_profiles"),
                f"{path}.redistribution_profiles",
                self.profile,
            ),
        )


def parse_virtual_routers(
    value: Any,
    firewall_serial: str,
    path: str,
) -> tuple[
    tuple[VirtualRouterConfiguration, ...] | None,
    tuple[PanoramaImportIssue, ...],
]:
    """Parse one firewall's virtual_routers array.

    Malformed entries are retained as raw JSON in issues.
    None means the complete array was unavailable.
    """
    parser = _RoutingParser(firewall_serial)

    if not isinstance(value, list):
        parser.issue(
            path,
            "Virtual-router collection is missing or is not an array",
            value,
            severity="error",
        )
        return None, tuple(parser.issues)

    routers = parser.items(value, path, parser.virtual_router)

    seen: set[str] = set()

    for router in routers:
        if router.name in seen:
            parser.issue(
                path,
                "Duplicate virtual-router name; both records retained",
                router.name,
            )

        seen.add(router.name)

    return routers, tuple(parser.issues)