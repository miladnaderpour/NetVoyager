from ipaddress import IPv4Network

from netvoyager_analysis.ipam.policy import classify_site_prefix


def test_connected_prefix_policy():
    assert classify_site_prefix(
        IPv4Network("10.0.0.0/12"),
        source="connected",
    ) == "ignored"

    assert classify_site_prefix(
        IPv4Network("10.32.0.0/13"),
        source="connected",
    ) == "candidate"

    assert classify_site_prefix(
        IPv4Network("10.40.0.0/20"),
        source="connected",
    ) == "eligible"

    assert classify_site_prefix(
        IPv4Network("10.127.24.7/32"),
        source="connected",
    ) == "ignored"


def test_static_routes_are_candidates():
    assert classify_site_prefix(
        IPv4Network("10.40.0.0/20"),
        source="static",
    ) == "candidate"


def test_bgp_prefixes_are_candidates():
    assert classify_site_prefix(
        IPv4Network("10.40.0.0/20"),
        source="bgp",
    ) == "candidate"