# 0001 - Keep network domain models simple

## Status

Accepted

## Context

NetworkDevice, NetworkScope, NetworkPrefix, AsPrefix and AutonomousSystem are reusable domain objects. Correlation, provenance and discovery logic must not make these base objects dependent on vendor integrations.

## Decision

- Keep `netvoyager-network` independent of vendor parsers and discovery workflows.
- Put relationship discovery and stores in `netvoyager-analysis`.
- Do not introduce dedicated device or scope stores merely to support the current script; the in-memory devices collection and scopes mapping are sufficient for now.
- Use `NetworkPrefixStore` for canonical prefix objects.

## Consequences

- Core models remain broadly reusable.
- Changes to current analysis functions can be staged without rebuilding the domain package.
- Scope UUID migration is an explicitly agreed exception to the current model shape (ADR 0006).
