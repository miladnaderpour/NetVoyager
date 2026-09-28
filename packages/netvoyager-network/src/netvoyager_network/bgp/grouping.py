"""Build autonomous systems and identify repeated IPv4 prefixes."""

import logging
from collections.abc import Iterable
from ipaddress import IPv4Network

from .models import AsGroupingResult, AsPrefix, AutonomousSystem


logger = logging.getLogger("netvoyager.network.bgp.grouping")


def group_as_prefixes(
    records: Iterable[AsPrefix],
) -> AsGroupingResult:
    """Organize prefix records into autonomous systems and duplicate groups.

    First group all input records by IPv4Network. For each prefix:
    - Add the network once to every distinct ASN represented in the group.
    - If the group contains multiple records, retain all of them in
      duplicates, including the first occurrence.

    Duplicate detection depends only on prefix equality. Records with
    different ASNs or AS paths still belong to the same duplicate group.
    Overlapping networks with different prefix lengths remain separate.

    Input is consumed once and is not modified. Result dictionaries are
    ordered by ASN and prefix respectively. Duplicate tuples preserve
    input encounter order. Empty input returns empty dictionaries.
    """
    records_by_prefix: dict[IPv4Network, list[AsPrefix]] = {}
    record_count = 0

    for record in records:
        records_by_prefix.setdefault(record.prefix, []).append(record)
        record_count += 1

    systems_by_asn: dict[int, AutonomousSystem] = {}
    duplicates: dict[IPv4Network, tuple[AsPrefix, ...]] = {}

    for prefix in sorted(records_by_prefix):
        prefix_records = records_by_prefix[prefix]
        asns = {record.asn for record in prefix_records}

        for asn in sorted(asns):
            autonomous_system = systems_by_asn.get(asn)

            if autonomous_system is None:
                autonomous_system = AutonomousSystem(asn=asn)
                systems_by_asn[asn] = autonomous_system

            autonomous_system.add_prefix(prefix)

        if len(prefix_records) > 1:
            duplicates[prefix] = tuple(prefix_records)

    result = AsGroupingResult(
        autonomous_systems={
            asn: systems_by_asn[asn]
            for asn in sorted(systems_by_asn)
        },
        duplicates=duplicates,
    )

    logger.info(
        "Prefix records organized into autonomous systems",
        extra={
            "record_count": record_count,
            "as_count": len(result.autonomous_systems),
            "unique_prefix_count": len(records_by_prefix),
            "duplicated_prefix_count": len(result.duplicates),
        },
    )

    return result