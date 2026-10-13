# 0004 - Control site-prefix assignments by association status

## Status

Accepted

## Context

Current `SitePrefixAssociation` is a specialized inventory-match result containing `site`, `prefix`, and supporting `devices`. Current `NetworkScope.prefix_ids` is populated by Step 5 without recording confidence; Step 6 consumes those IDs for ASN correlation.

## Decision

- Keep the existing `SitePrefixAssociation` as the inventory matching **result** model; do not pretend it is already a general-purpose association registry.
- Introduce a separate analysis-level `PrefixSiteAssociation` concept for per-prefix, per-scope status.
- Statuses: `candidate`, `inferred`, `validated`.
- `candidate` does **not** enter `NetworkScope.prefix_ids` and does not seed further automatic inference.
- `inferred` **does** enter `NetworkScope.prefix_ids` but does **not** seed further automatic inference.
- `validated` enters `NetworkScope.prefix_ids` and **can** seed further automatic inference.
- Preserve independently validated decisions rather than silently downgrading them from weaker later observations.
- Inference in one run must not recursively bootstrap from new inferences made in that run.

## Consequences

- `NetworkScope.prefix_ids` remains an accepted working view, not the holder of status.
- Existing BGP/inventory-generated associations should not automatically be mislabeled manually validated.
- The accepted projection and the authoritative association state must remain synchronized.
