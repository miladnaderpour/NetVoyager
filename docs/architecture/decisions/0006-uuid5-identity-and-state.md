# 0006 - Use deterministic UUIDv5 for identity and configuration state

## Status

Accepted

## Context

New UUIDv4 values on each discovery run prevent direct cross-run identity comparison. The project needs to detect technical configuration changes even when a prefix stays the same.

## Decision

- Use deterministic **UUIDv5** for both an object's logical **identity** and **state**.
- Define explicit identity fields and state fields **for each model/dataclass**; do not use a single universal property list.
- Compute identity and state UUIDs from canonical, normalized and versioned inputs under fixed namespaces, including a model-type discriminator.
- State UUID input includes logical identity and designated state fields; unchanged identity+state yields the same UUID across runs.
- Administrative labels such as static-route names are not, by default, the technical basis for change detection.
- Route changes should be judged using meaningful routing properties (destination, next hop, distance, metric, interface and relevant context); account for parallel same-destination routes.
- Preserve individual per-run observations separately from deterministic logical identity/state fingerprints.
- Convert `NetworkScope.scope_id` to UUID and use UUID for `PrefixSiteAssociation.scope_id`, while retaining a human-readable site reference/code for matching and display.

## Consequences

- Same entity/same state can be recognized across runs without a UUIDv4 registry lookup.
- Same identity/different state indicates a change; different identity calls for new/removed or explicit reconciliation where natural identity is genuinely ambiguous.
- Exact field sets, canonical serialization and migration of string scope IDs still require model-by-model specification before implementation.
