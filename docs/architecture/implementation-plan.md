# Implementation Plan and Field Policies To Finalize

**Purpose:** a checkpoint for the next NetVoyager design/coding session. Accepted design principles live in ADRs; the items here are **not** silently locked.

## Proposed implementation order

1. Inventory existing model/dataclass fields and identity context for `NetworkPrefix`, `NetworkScope`, `NetworkDevice`, `AsPrefix`, Panorama `StaticRoute`, `InterfaceAddress`; capture future DHCP requirements without inventing a DHCP model prematurely.
2. Specify, review and test identity/state field policies and canonical serialization (UUIDv5 fixed namespace, model discriminator, field-schema version, normalization, handling of `None`, set ordering and context).
3. Define two separate analysis-layer relationship models and their lookup/store APIs: `SourcePrefixAssociation` and `PrefixSiteAssociation`. Keep every source observation link; make site association uniqueness per `(prefix_id, scope_id)` in current state.
4. Implement string-to-UUID `NetworkScope.scope_id` migration and retain human site codes. Update builders, scope dictionaries, logging, findings, and test fixtures consistently.
5. During BGP canonicalization, preserve each `AsPrefix` → `NetworkPrefix` relationship. Refactor ASN processing to use these associations instead of reconstructing `asns_by_prefix` from CIDR; preserve current findings/ASN semantics.
6. Convert Step 5 inventory-match results to managed `inferred` site-prefix relationships. Project inferred/validated into `NetworkScope.prefix_ids`; only validated associations may seed further automated inference.
7. Enrich canonical prefixes and source associations using Panorama selected connected and static routes. Build site candidates from a frozen independently supported site context; permit multi-site shared-supernet candidates and more-specific validated child prefixes.
8. Add run completeness metadata, comparable snapshots and technical state/relationship diffs. Verify interface moves, next-hop changes, site-code renames, parallel static routes, partial collection and repeat imports.
9. Integrate DHCP scope ingestion when ready as an additional source of canonical prefixes; it must not imply DHCP server physical-site ownership.

## Field-level questions (must be answered from actual models)

- Exact UUIDv5 identity fields vs state fields **per dataclass**, including contextual keys not currently stored on observations.
- Collision/ambiguity policy for multiple same-destination static routes (including ECMP/parallel entries). Name is metadata, not a default technical identity.
- Canonical prefix context: current `NetworkPrefixStore` is keyed by CIDR; design future VRF/overlapping address-space support before claiming globally unique CIDR identity.
- Whether source observation objects all have UUID fields and how run-specific occurrence identifiers are represented.
- Association store layout and how the stores expose bidirectional queries; transactional synchronization with `NetworkScope.prefix_ids`.
- How existing Step 5 associations are initially tagged `inferred` and how manual validation is recorded.
- How the current ASN correlation handles shared prefixes/multiple origins after migration (do not silently change current findings).
- Snapshot persistence location and mechanisms for recognizing a complete vs partial collector run.

## Design test scenarios

| Scenario | Expected behavior |
|---|---|
| Same complete input in two runs | Same identity and state UUIDv5 values; no change |
| Static route moves `ethernet1/3` → `ethernet1/4` | Same route where identity policy permits; different state; field-level egress change |
| Only static route label changes | Not treated as technical route change under agreed policy |
| Multiple technical routes to same destination | All remain distinguishable; changes are not mispaired |
| Five AsPrefix observations same prefix/ASN | One canonical prefix; five retained source links; distinct ASN assignment set |
| Prefix candidate for Site A + Site B | Two candidate relations, neither automatically projected into scope prefixes |
| More specific `/23` validated for Site A | Site A gets accepted `/23`; shared parent candidate need not be deleted |
| Partial Panorama collection omits a route | No confirmed removal inferred from incomplete data |
| DHCP server hosts remote scopes | DHCP scope prefixes discovered; no automatic local-site assignment |

## Device discovery and inventory evidence workstream (2026-10-16)

Keep the earlier IPAM implementation order above as a separate outstanding workstream. The following items are **planned or require verification**, not implicitly complete:

1. Inspect current checked-in `netvoyager-analysis/devices/{processing,matching,enrichment}` and `devices/discovery/{models,relationships,store,evidence}`; compare with proposed session code before assuming integration.
2. Verify baseline Excel import: one device per nonempty resolved name; missing name warning and evidence-only outcome; all source rows and duplicate issues preserved.
3. Implement/import run provenance (file, worksheet, row, run identity) and distinguish repeated evidence observations from device technical-state changes (ADR-0010).
4. Harden discovery registry against uncontrolled candidate/relationship mutation; centralize lifecycle and relationship transition validation.
5. Implement append-only, evidence-backed candidate resolution reversal; check canonical device existence, preserve multiple candidates per device and keep decision history.
6. Define source-specific strong physical identity rules; ensure stack-level reports cannot masquerade as single-member identity.
7. Decide canonical name generation for devices not present in Excel; preserve existing `NetworkDevice` UUIDv5 contract and avoid name collisions.
8. Build reconciliation/promotion service, then integrate with `netvoyager-discovery` and vendor APIs/CLI collectors.
9. Validate complete evidence lookup, including candidates resolved to a device and relationship/decision evidence as separately scoped.
10. Run focused and cross-package regressions and compare known inventory/BGP/Panorama baselines; no passing integrated results have been established by this documentation pass.
