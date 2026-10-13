# 0002 - Separate prefix relationships into two layers

## Status

Accepted

## Context

A canonical prefix can be observed through BGP, Palo Alto static routes or interface addresses, and later DHCP scopes. Observing a prefix is different from associating it with a site.

## Decision

- **Layer 1 — source-to-canonical:** retain a separate navigable relationship for every individual source observation associated with a canonical `NetworkPrefix`.
- **Layer 2 — canonical-to-site:** manage each `(prefix_id, scope_id)` site relationship separately, including its candidate/inferred/validated status.
- Canonicalize a network once and reuse its `NetworkPrefix` object in the current address-space context.
- Establish source relationships during canonicalization, not by later reconstructing source links via CIDR searches.
- Do not use `EvidenceStore` as a relationship lookup database; it remains provenance/evidence only.

## Consequences

- One prefix can have several BGP, static, connected or DHCP observation links without duplicate canonical objects.
- Site attribution can evolve independently of discovery sources.
- Store implementation details remain to be implemented (see implementation plan).
