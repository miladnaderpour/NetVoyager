"""Models for BGP analysis results."""

from dataclasses import dataclass

from netvoyager_network.bgp.models import (
    AsPrefix,
    AutonomousSystem,
)


@dataclass(frozen=True, slots=True)
class BgpProcessingResult:
    """Result of processing parsed BGP route observations.

    as_prefixes contains BGP prefix observations with a usable origin ASN.

    Local routes are included in as_prefixes when a local ASN was supplied
    to BGP processing.

    autonomous_systems contains the unique AutonomousSystem objects derived
    from the resulting AsPrefix observations.

    local_route_count counts observations explicitly identified as local
    routes, regardless of whether a local ASN was available.

    unknown_origin_count counts observations for which no usable origin ASN
    could be determined.
    """

    as_prefixes: tuple[AsPrefix, ...]
    autonomous_systems: tuple[AutonomousSystem, ...]

    local_route_count: int
    unknown_origin_count: int