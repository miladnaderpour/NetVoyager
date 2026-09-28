"""Check BGP grouping behavior using small, explicit datasets.

Run this script from the project environment where netvoyager_network
is installed. No inventory files or network access are required.

The checks verify AS membership and preservation of complete duplicate
groups without interpreting whether repeated prefixes are valid.
"""

import unittest
from ipaddress import IPv4Network

from netvoyager_network import group_as_prefixes
from netvoyager_network.bgp.models import AsPrefix


class TestAsPrefixGrouping(unittest.TestCase):
    """Verify grouping rules and duplicate preservation."""

    def test_unique_prefixes(self) -> None:
        """Unique prefixes belong to their AS without duplicate entries."""
        first = IPv4Network("10.1.0.0/24")
        second = IPv4Network("10.2.0.0/24")
        third = IPv4Network("10.3.0.0/24")

        result = group_as_prefixes(
            [
                AsPrefix(asn=65002, prefix=third),
                AsPrefix(asn=65001, prefix=first),
                AsPrefix(asn=65001, prefix=second),
            ]
        )

        self.assertEqual(
            list(result.autonomous_systems),
            [65001, 65002],
        )
        self.assertEqual(
            result.autonomous_systems[65001].prefixes,
            frozenset({first, second}),
        )
        self.assertEqual(
            result.autonomous_systems[65002].prefixes,
            frozenset({third}),
        )
        self.assertEqual(result.duplicates, {})

    def test_identical_records(self) -> None:
        """Repeated identical records are all retained, including the first."""
        prefix = IPv4Network("10.1.0.0/24")
        record = AsPrefix(asn=65001, prefix=prefix)

        result = group_as_prefixes([record, record, record])

        self.assertEqual(
            result.autonomous_systems[65001].prefixes,
            frozenset({prefix}),
        )
        self.assertEqual(
            result.duplicates,
            {prefix: (record, record, record)},
        )

    def test_same_asn_with_different_paths(self) -> None:
        """Different paths remain intact in the duplicate prefix group."""
        prefix = IPv4Network("10.1.0.0/24")
        records = [
            AsPrefix(
                asn=65001,
                prefix=prefix,
                as_path=(65534, 65001),
            ),
            AsPrefix(
                asn=65001,
                prefix=prefix,
                as_path=(65002, 65001),
            ),
        ]

        result = group_as_prefixes(records)

        self.assertEqual(set(result.autonomous_systems), {65001})
        self.assertEqual(
            result.autonomous_systems[65001].prefixes,
            frozenset({prefix}),
        )
        self.assertEqual(
            result.duplicates[prefix],
            tuple(records),
        )

    def test_same_prefix_with_multiple_asns(self) -> None:
        """A repeated prefix belongs once to every represented ASN."""
        prefix = IPv4Network("10.1.0.0/24")
        records = [
            AsPrefix(asn=65002, prefix=prefix),
            AsPrefix(asn=65001, prefix=prefix),
            AsPrefix(
                asn=65002,
                prefix=prefix,
                as_path=(65534, 65002),
            ),
        ]

        result = group_as_prefixes(records)

        self.assertEqual(set(result.autonomous_systems), {65001, 65002})

        for asn in (65001, 65002):
            with self.subTest(asn=asn):
                self.assertEqual(
                    result.autonomous_systems[asn].asn,
                    asn,
                )
                self.assertEqual(
                    result.autonomous_systems[asn].prefixes,
                    frozenset({prefix}),
                )

        self.assertEqual(
            result.duplicates[prefix],
            tuple(records),
        )

    def test_overlapping_prefixes(self) -> None:
        """Containment alone does not make two networks duplicates."""
        parent = IPv4Network("10.1.0.0/16")
        child = IPv4Network("10.1.2.0/24")

        result = group_as_prefixes(
            [
                AsPrefix(asn=65001, prefix=parent),
                AsPrefix(asn=65001, prefix=child),
            ]
        )

        self.assertEqual(
            result.autonomous_systems[65001].prefixes,
            frozenset({parent, child}),
        )
        self.assertEqual(result.duplicates, {})

    def test_interleaved_records_from_generator(self) -> None:
        """One-pass input preserves encounter order within duplicate groups."""
        first = IPv4Network("10.1.0.0/24")
        second = IPv4Network("10.2.0.0/24")

        records = [
            AsPrefix(asn=65002, prefix=second),
            AsPrefix(asn=65001, prefix=first),
            AsPrefix(asn=65003, prefix=second),
            AsPrefix(asn=65001, prefix=first),
        ]

        result = group_as_prefixes(record for record in records)

        self.assertEqual(list(result.duplicates), [first, second])
        self.assertEqual(
            result.duplicates[first],
            (records[1], records[3]),
        )
        self.assertEqual(
            result.duplicates[second],
            (records[0], records[2]),
        )

    def test_empty_input(self) -> None:
        """Empty input produces empty AS and duplicate dictionaries."""
        result = group_as_prefixes([])

        self.assertEqual(result.autonomous_systems, {})
        self.assertEqual(result.duplicates, {})


if __name__ == "__main__":
    unittest.main(verbosity=2)