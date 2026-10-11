"""Parse Palo Alto BGP CLI output."""

import re
from dataclasses import dataclass, field
from ipaddress import IPv4Address, IPv4Network

from netvoyager_core.logging import get_logger

from .models import (
    BgpRibDump,
    BgpRibResult,
    BgpRoute,
    BgpSummary,
    UnparsedLine,
)


logger = get_logger("paloalto.bgp.parser")


@dataclass(slots=True)
class _Section:
    """Mutable state used while parsing one local-RIB section."""

    name: str
    router_id: int
    routes: list[BgpRoute] = field(
        default_factory=list
    )
    unparsed_lines: list[UnparsedLine] = field(
        default_factory=list
    )
    total_routes_shown: int | None = None


SUMMARY_ROUTER_ID_RE = re.compile(
    r"[ \t]*router id:[ \t]*(?P<router_id>\S+)[ \t]*",
    re.IGNORECASE,
)

SUMMARY_VIRTUAL_ROUTER_RE = re.compile(
    r"[ \t]*virtual router:[ \t]*(?P<virtual_router>.+?)[ \t]*",
    re.IGNORECASE,
)

SUMMARY_LOCAL_AS_RE = re.compile(
    r"[ \t]*local as:[ \t]*(?P<local_as>[0-9]+)[ \t]*",
    re.IGNORECASE,
)


HEADER_RE = re.compile(
    r"[ \t]*VIRTUAL ROUTER:[ \t]*(?P<name>.+?)"
    r"[ \t]*\(id[ \t]+(?P<id>[0-9]+)\)[ \t]*"
)

ROUTE_RE = re.compile(
    r"[ \t]*(?P<marker>\*)?[ \t]*"
    r"(?P<prefix>(?:[0-9]{1,3}\.){3}[0-9]{1,3}/"
    r"(?:3[0-2]|[12][0-9]|[0-9]))"
    r"[ \t]+"
    r"(?:(?P<next_hop>(?:[0-9]{1,3}\.){3}[0-9]{1,3})[ \t]+)?"
    r"(?P<peer>\S+)"
    r"(?:[ \t]+\S+){5}"
    r"(?:[ \t]+(?P<as_path>[0-9]+(?:,[0-9]+)*))?"
    r"[ \t]*"
)

FOOTER_RE = re.compile(
    r"[ \t]*total routes shown:[ \t]*(?P<count>[0-9]+)[ \t]*"
)

PAGE_RE = re.compile(
    r"lines[ \t]+[0-9]+-[0-9]+"
)

PROMPT_RE = re.compile(
    r"\S+@\S+(?:\([^)]*\))?[>#][ \t]*"
)


def parse_bgp_summary(
    raw_text: str,
) -> BgpSummary:
    """Parse Palo Alto `show routing protocol bgp summary` output.

    Extract the virtual-router name, router ID, and local ASN.

    The virtual-router name is required because it identifies the routing
    context.

    router_id and local_asn remain None when the corresponding values are
    absent from the supplied output.

    Raise ValueError when no virtual-router field is present or when a
    reported router ID is not a valid IPv4 address.
    """
    virtual_router: str | None = None
    router_id: IPv4Address | None = None
    local_asn: int | None = None

    for line in raw_text.splitlines():
        if virtual_router is None:
            match = SUMMARY_VIRTUAL_ROUTER_RE.fullmatch(
                line
            )

            if match is not None:
                virtual_router = match.group(
                    "virtual_router"
                ).strip()

                continue

        if router_id is None:
            match = SUMMARY_ROUTER_ID_RE.fullmatch(
                line
            )

            if match is not None:
                router_id_text = match.group(
                    "router_id"
                )

                try:
                    router_id = IPv4Address(
                        router_id_text
                    )
                except ValueError as exc:
                    raise ValueError(
                        "Invalid BGP router ID: "
                        f"{router_id_text}"
                    ) from exc

                continue

        if local_asn is None:
            match = SUMMARY_LOCAL_AS_RE.fullmatch(
                line
            )

            if match is not None:
                local_asn = int(
                    match.group(
                        "local_as"
                    )
                )

    if virtual_router is None:
        raise ValueError(
            "No virtual router was found in BGP summary"
        )

    result = BgpSummary(
        virtual_router=virtual_router,
        router_id=router_id,
        local_asn=local_asn,
    )

    logger.info(
        "BGP summary parsed",
        extra={
            "virtual_router": result.virtual_router,
            "router_id": (
                str(result.router_id)
                if result.router_id is not None
                else None
            ),
            "local_asn": result.local_asn,
        },
    )

    return result


def _parse_header(
    line: str,
) -> tuple[str, int] | None:
    """Parse a local-RIB virtual-router section header."""
    match = HEADER_RE.fullmatch(
        line
    )

    if match is None:
        return None

    return (
        match.group("name"),
        int(
            match.group("id")
        ),
    )


def _is_table_decoration(
    line: str,
) -> bool:
    """Return whether a line is non-route table decoration."""
    stripped = line.strip()

    return (
        not stripped
        or set(stripped) == {"="}
        or (
            stripped.startswith("Prefix")
            and "AS-Path" in stripped
        )
        or PAGE_RE.fullmatch(
            stripped
        ) is not None
        or PROMPT_RE.fullmatch(
            stripped
        ) is not None
    )


def _parse_route(
    line: str,
    line_number: int,
) -> BgpRoute | UnparsedLine:
    """Parse one local-RIB route line."""
    match = ROUTE_RE.fullmatch(
        line
    )

    if match is None:
        return UnparsedLine(
            line_number=line_number,
            reason="Unrecognized line format",
            raw_line=line,
        )

    next_hop_text = match.group(
        "next_hop"
    )

    as_path_text = match.group(
        "as_path"
    )

    try:
        prefix = IPv4Network(
            match.group(
                "prefix"
            )
        )

        next_hop = (
            IPv4Address(
                next_hop_text
            )
            if next_hop_text
            else None
        )

    except ValueError:
        return UnparsedLine(
            line_number=line_number,
            reason="Invalid prefix or next-hop address",
            raw_line=line,
        )

    return BgpRoute(
        prefix=prefix,
        next_hop=next_hop,
        peer=match.group(
            "peer"
        ),
        as_path=(
            tuple(
                int(asn)
                for asn in as_path_text.split(",")
            )
            if as_path_text
            else ()
        ),
        marker=(
            "*"
            if match.group("marker")
            else None
        ),
        line_number=line_number,
        raw_line=line,
    )


def _parse_footer(
    line: str,
) -> int | None:
    """Parse the reported local-RIB route count."""
    match = FOOTER_RE.fullmatch(
        line
    )

    if match is None:
        return None

    return int(
        match.group(
            "count"
        )
    )


def _finish_section(
    section: _Section,
) -> BgpRibResult:
    """Convert mutable parser state into one immutable RIB result."""
    parsed_count = len(
        section.routes
    )

    reported_count = (
        section.total_routes_shown
    )

    log_fields = {
        "virtual_router_id": section.router_id,
        "parsed_routes": parsed_count,
        "reported_routes": reported_count,
        "unparsed_lines": len(
            section.unparsed_lines
        ),
    }

    if (
        reported_count is not None
        and parsed_count != reported_count
    ):
        logger.warning(
            "BGP RIB route count differs from footer",
            extra=log_fields,
        )

    else:
        logger.info(
            "BGP RIB section parsed",
            extra=log_fields,
        )

    return BgpRibResult(
        virtual_router=section.name,
        virtual_router_id=section.router_id,
        routes=tuple(
            section.routes
        ),
        total_routes_shown=reported_count,
        unparsed_lines=tuple(
            section.unparsed_lines
        ),
    )


def parse_loc_rib(
    raw_text: str,
) -> BgpRibDump:
    """Parse all virtual-router sections in a Palo Alto BGP local RIB.

    Preserve parsed route order and retain unrecognized content as
    UnparsedLine objects.

    Each virtual-router section becomes a BgpRibResult. Content that appears
    outside a virtual-router section is retained at the dump level.

    Raise ValueError when no virtual-router sections are found.
    """
    lines = raw_text.splitlines()

    logger.debug(
        "Starting BGP local RIB parse",
        extra={
            "line_count": len(lines)
        },
    )

    sections: list[BgpRibResult] = []
    global_unparsed: list[UnparsedLine] = []

    current: _Section | None = None

    for line_number, line in enumerate(
        lines,
        start=1,
    ):
        header = _parse_header(
            line
        )

        if header is not None:
            if current is not None:
                sections.append(
                    _finish_section(
                        current
                    )
                )

            name, router_id = header

            current = _Section(
                name=name,
                router_id=router_id,
            )

            logger.debug(
                "Virtual router section started",
                extra={
                    "line_number": line_number,
                    "virtual_router": name,
                    "virtual_router_id": router_id,
                },
            )

            continue

        footer_count = _parse_footer(
            line
        )

        if footer_count is not None:
            if current is not None:
                current.total_routes_shown = (
                    footer_count
                )

            else:
                global_unparsed.append(
                    UnparsedLine(
                        line_number=line_number,
                        reason=(
                            "Footer before router header"
                        ),
                        raw_line=line,
                    )
                )

            continue

        if _is_table_decoration(
            line
        ):
            continue

        if current is None:
            global_unparsed.append(
                UnparsedLine(
                    line_number=line_number,
                    reason=(
                        "Content before router header"
                    ),
                    raw_line=line,
                )
            )

            continue

        parsed = _parse_route(
            line,
            line_number,
        )

        if isinstance(
            parsed,
            BgpRoute,
        ):
            current.routes.append(
                parsed
            )

        else:
            current.unparsed_lines.append(
                parsed
            )

            logger.debug(
                "BGP RIB line could not be parsed",
                extra={
                    "line_number": line_number,
                    "reason": parsed.reason,
                },
            )

    if current is not None:
        sections.append(
            _finish_section(
                current
            )
        )

    if not sections:
        raise ValueError(
            "No virtual router sections were found"
        )

    result = BgpRibDump(
        routers=tuple(
            sections
        ),
        unparsed_lines=tuple(
            global_unparsed
        ),
    )

    logger.info(
        "BGP local RIB parse completed",
        extra={
            "section_count": len(
                result.routers
            ),
            "route_count": sum(
                len(section.routes)
                for section in result.routers
            ),
            "global_unparsed_count": len(
                result.unparsed_lines
            ),
        },
    )

    return result