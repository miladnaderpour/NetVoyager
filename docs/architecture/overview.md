# NetVoyager Architecture Overview

NetVoyager should remain simple in its domain layer while supporting reproducible, vendor-independent network discovery and evolving site/prefix knowledge. This is an **agreed design target**, not a claim that every component already exists in code.

## Major Components

### Domain (`netvoyager-network`)

Simple models including `NetworkDevice`, `NetworkScope`, `NetworkPrefix`, `AsPrefix`, and `AutonomousSystem`. `NetworkScope.scope_id` is to become a UUID; human-readable site codes remain distinct.

### Source ingestion

- `netvoyager-import`: Excel network inventory.
- `netvoyager-paloalto`: BGP local RIB; Panorama inventory with connected interface addresses and static routes.
- Future: Microsoft DHCP scope ingestion.

### Analysis (`netvoyager-analysis`)

- Canonicalization creates/reuses `NetworkPrefix` via `NetworkPrefixStore`.
- **Layer 1: source-to-canonical:** one navigable link per individual BGP/static/connected/DHCP observation.
- **Layer 2: canonical-to-site:** site-prefix association with `candidate`, `inferred`, `validated` status.
- `EvidenceStore` tracks provenance, not operational relationship traversal.
- `FindingStore` tracks ambiguity/conflicts.
- Existing `SitePrefixAssociation` remains a Step 5 inventory-analysis result distinct from the proposed general site association.

### Repeatable discovery (designed, not yet built)

Each model/dataclass declares identity and state fields. Deterministic UUIDv5 fingerprints enable cross-run matching and change detection. Discovery snapshots must cover objects **and** relationships; partial collection does not imply deletion.

## Target data flow

```text
Inventory → NetworkDevice → NetworkScope baseline
BGP AsPrefix ───────────────┐
Panorama StaticRoute ───────┤
Panorama InterfaceAddress ──┼→ NetworkPrefixStore (canonical prefixes)
DHCP Scope (future) ────────┘             │
          source-to-canonical association layer
                                         │
Inventory device/IP + firewall site/prefix context
                                         ↓
          canonical-to-site association layer
               candidate | inferred | validated
                                         ↓
             NetworkScope.prefix_ids projection
                                         ↓
         Site ↔ ASN via retained AsPrefix links

Discovery runs + normalized UUIDv5 identity/state
  → comparable snapshots → change analysis
```

## Existing implementation vs target

| Area | Present in supplied integration | Target / planned |
|---|---|---|
| Devices / site scopes | In-memory `devices` / `scopes` | Scope UUID migration |
| Prefix objects | `NetworkPrefixStore` | Reuse as-is |
| BGP canonicalization | `process_network_prefixes()` | Persist direct source-prefix links |
| Site matching | `analyze_site_prefixes()` returns `SitePrefixAssociation` and updates scopes | Register association statuses; controlled projection |
| ASN mapping | `associate_scope_autonomous_systems()` reindexes AsPrefix by CIDR | Consume preserved source associations |
| Panorama | Identity/scope resolution and connected/static candidates | Canonical enrichment and association inference |
| Discovery history | Not implemented in integration script | UUIDv5 field policies, run snapshots, comparisons |

## References

See `decisions/` for accepted ADRs, `current-workflow.md` for the presently observed code path, and `implementation-plan.md` for remaining decisions and sequencing.
