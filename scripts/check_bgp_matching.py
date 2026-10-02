"""Check BGP prefix matching using small, explicit datasets.

Run this script from the project environment where netvoyager_network
is installed. No inventory files or network access are required.

The checks verify longest-prefix selection and preservation of all
matching records without selecting an ASN or interpreting AS paths.
"""

import unittest
from ipaddress import IPv4Address, IPv4Network

from netvoyager_network.bgp.matching import find_most_specific_matches
from netvoyager_network.bgp.models import AsPrefix


class TestAsPrefixMatching(unittest.TestCase):
    """Verify longest-prefix matching and record preservation."""

    def test_longest_prefix(self) -> None:
        """A more-specific match replaces earlier, less-specific matches."""
        records = [
            AsPrefix(asn=65001, prefix=IPv4Network("10.0.0.0/8")),
            AsPrefix(asn=65002, prefix=IPv4Network("10.1.0.0/16")),
            AsPrefix(asn=65003, prefix=IPv4Network("10.1.2.0/24")),
            AsPrefix(asn=65004, prefix=IPv4Network("10.1.0.0/16")),
            AsPrefix(asn=65005, prefix=IPv4Network("10.1.3.50/32")),
        ]

        result = find_most_specific_matches(
            IPv4Address("10.1.2.50"),
            records,
        )

        self.assertEqual(result, (records[2],))

    def test_identical_records(self) -> None:
        """Repeated identical records are retained with full multiplicity."""
        record = AsPrefix(
            asn=65001,
            prefix=IPv4Network("10.1.2.0/24"),
        )

        result = find_most_specific_matches(
            IPv4Address("10.1.2.50"),
            [record, record, record],
        )

        self.assertEqual(result, (record, record, record))

    def test_same_asn_with_different_paths(self) -> None:
        """Paths remain unchanged, including unavailable and empty paths."""
        prefix = IPv4Network("10.1.2.0/24")
        records = [
            AsPrefix(asn=65001, prefix=prefix, as_path=None),
            AsPrefix(asn=65001, prefix=prefix, as_path=()),
            AsPrefix(
                asn=65001,
                prefix=prefix,
                as_path=(65534, 65001),
            ),
            AsPrefix(
                asn=65001,
                prefix=prefix,
                as_path=(65002, 65001, 65001),
            ),
        ]

        result = find_most_specific_matches(
            IPv4Address("10.1.2.50"),
            records,
        )

        self.assertEqual(result, tuple(records))

        for actual, original in zip(result, records):
            with self.subTest(as_path=original.as_path):
                self.assertIs(actual, original)

    def test_same_prefix_with_multiple_asns(self) -> None:
        """All candidate ASNs remain in encounter order without selection."""
        prefix = IPv4Network("10.1.2.0/24")
        records = [
            AsPrefix(asn=65002, prefix=prefix),
            AsPrefix(asn=65001, prefix=prefix),
            AsPrefix(
                asn=65002,
                prefix=prefix,
                as_path=(65534, 65002),
            ),
        ]

        result = find_most_specific_matches(
            IPv4Address("10.1.2.50"),
            records,
        )

        self.assertEqual(result, tuple(records))
        self.assertEqual({record.asn for record in result}, {65001, 65002})

    def test_interleaved_records_from_generator(self) -> None:
        """One-pass input retains separated best matches in encounter order."""
        prefix = IPv4Network("10.1.2.0/24")
        records = [
            AsPrefix(asn=65001, prefix=IPv4Network("10.0.0.0/8")),
            AsPrefix(asn=65003, prefix=prefix),
            AsPrefix(asn=65004, prefix=IPv4Network("10.2.0.0/16")),
            AsPrefix(asn=65002, prefix=prefix),
            AsPrefix(asn=65005, prefix=IPv4Network("10.1.0.0/16")),
            AsPrefix(asn=65003, prefix=prefix),
        ]

        result = find_most_specific_matches(
            IPv4Address("10.1.2.50"),
            (record for record in records),
        )

        self.assertEqual(result, (records[1], records[3], records[5]))

    def test_network_boundaries(self) -> None:
        """Both network and broadcast addresses belong to the prefix."""
        record = AsPrefix(
            asn=65001,
            prefix=IPv4Network("10.1.2.0/24"),
        )

        for address in ("10.1.2.0", "10.1.2.255"):
            with self.subTest(address=address):
                result = find_most_specific_matches(
                    IPv4Address(address),
                    [record],
                )

                self.assertEqual(result, (record,))

    def test_default_and_host_prefixes(self) -> None:
        """A /32 wins for its address; /0 matches other addresses."""
        default = AsPrefix(
            asn=65001,
            prefix=IPv4Network("0.0.0.0/0"),
        )
        host = AsPrefix(
            asn=65002,
            prefix=IPv4Network("10.1.2.50/32"),
        )
        records = [default, host]

        cases = [
            ("10.1.2.50", (host,)),
            ("10.1.2.51", (default,)),
        ]

        for address, expected in cases:
            with self.subTest(address=address):
                result = find_most_specific_matches(
                    IPv4Address(address),
                    records,
                )

                self.assertEqual(result, expected)

    def test_input_unchanged(self) -> None:
        """Matching leaves the supplied collection and records unchanged."""
        records = [
            AsPrefix(asn=65001, prefix=IPv4Network("10.0.0.0/8")),
            AsPrefix(asn=65002, prefix=IPv4Network("10.1.2.0/24")),
        ]
        original_records = tuple(records)

        result = find_most_specific_matches(
            IPv4Address("10.1.2.50"),
            records,
        )

        self.assertEqual(tuple(records), original_records)
        self.assertEqual(result, (original_records[1],))
        self.assertIs(result[0], original_records[1])

    def test_no_matching_prefix(self) -> None:
        """An address outside every supplied prefix returns an empty tuple."""
        records = [
            AsPrefix(asn=65001, prefix=IPv4Network("10.1.0.0/16")),
            AsPrefix(asn=65002, prefix=IPv4Network("10.2.0.0/16")),
        ]

        result = find_most_specific_matches(
            IPv4Address("192.168.1.50"),
            records,
        )

        self.assertEqual(result, ())

    def test_empty_input(self) -> None:
        """Empty input returns an empty tuple."""
        result = find_most_specific_matches(
            IPv4Address("10.1.2.50"),
            [],
        )

        self.assertEqual(result, ())


if __name__ == "__main__":
    unittest.main(verbosity=2)