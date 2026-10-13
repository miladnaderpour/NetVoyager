
from ipaddress import IPv4Network
from uuid import uuid4

from netvoyager_network.bgp.models import AsPrefix


def test_as_prefix_deterministic_identity():
    source_id = uuid4()
    prefix = IPv4Network("10.249.0.0/24")

    first = AsPrefix(
        source_id=source_id,
        asn=65520,
        prefix=prefix,
    )

    second = AsPrefix(
        source_id=source_id,
        asn=65520,
        prefix=prefix,
    )

    assert first.id == second.id
    assert first.id.version == 5


def test_different_sources_have_different_ids():
    prefix = IPv4Network("10.249.0.0/24")

    first = AsPrefix(
        source_id=uuid4(),
        asn=65520,
        prefix=prefix,
    )

    second = AsPrefix(
        source_id=uuid4(),
        asn=65520,
        prefix=prefix,
    )

    assert first.id != second.id


def test_as_path_and_origin_do_not_change_identity():
    source_id = uuid4()
    prefix = IPv4Network("10.249.0.0/24")

    first = AsPrefix(
        source_id=source_id,
        asn=65520,
        prefix=prefix,
        as_path=(65534, 65520),
        origin="igp",
    )

    second = AsPrefix(
        source_id=source_id,
        asn=65520,
        prefix=prefix,
        as_path=(65534, 65520, 65520),
        origin="egp",
    )

    assert first.id == second.id
