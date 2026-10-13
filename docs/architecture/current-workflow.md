# Current NetVoyager Analysis Workflow (as of 2026-10-12)

This describes the supplied `test_panorama_scope_analysis.py`, not the future target design.

1. **Import inventory:** `read_network_devices()` yields observations; `process_device_observations()` builds `NetworkDevice` objects and evidence.
2. **Build site scopes:** `build_site_scopes(devices)` groups devices by the string site code into an in-memory `scopes` mapping.
3. **Parse BGP:** `parse_loc_rib()` and `parse_bgp_summary()` select `vpn_intern`; `process_bgp_routes()` builds `AsPrefix` and `AutonomousSystem` results.
4. **Canonicalize prefixes:** `process_network_prefixes(as_prefixes, network_prefix_store, evidence_store)` creates/reuses canonical `NetworkPrefix` objects. The operational `AsPrefix` link is *not* retained as a separate navigable analysis association in the script.
5. **Site-prefix matching:** `analyze_site_prefixes()` matches inventory management IPs against eligible canonical prefixes, returns `SitePrefixAnalysisResult.associations` (each has `site`, `prefix`, `devices`), and populates `scope.prefix_ids`. The script excludes 567 BGP `/32` prefixes in the cited test run, and uses a `/16` baseline threshold.
6. **ASN correlation:** `associate_scope_autonomous_systems()` creates `asns_by_prefix: dict[IPv4Network, set[int]]` from `AsPrefix` observations, then resolves each scope prefix ID via `NetworkPrefixStore`, exact-matches CIDR and calls `scope.add_asn()`. Ambiguities create findings.
7. **Panorama:** `parse_panorama_inventory()` parses firewall metadata, interface addresses, static routes. `resolve_firewall_identities()` matches inventory devices. `resolve_firewall_scopes()` checks existing canonical/site associations for connected networks and records selected static routes as validation candidates; it does not currently enrich canonical prefixes/site scope assignments.
8. **Report:** findings, site-prefix associations, store sizes and evidence totals are logged.

## Current stores/collections

| Name | Role |
|---|---|
| `NetworkPrefixStore` | Canonical prefix objects |
| `EvidenceStore` | Source provenance and evidence relations, not relationship lookup |
| `FindingStore` | Findings and conflict details |
| `devices` | In-memory devices collection |
| `scopes` | In-memory site dictionary |
| `bgp_result.autonomous_systems` | In-memory ASN grouping |
| `analysis_result.associations` | Step 5 matching output, **not** a generalized status store |
| `resolutions` | Panorama firewall resolution output |

