
# ADR-0011 — Storage Architecture and Model Separation

## Status

Accepted

## Date

2026-10-18

## Context

NetVoyager is evolving into a modular network discovery,
analysis, inventory, and automation platform.

The platform will eventually support API, CLI, worker,
scheduler, and web applications.

The analysis packages must remain independent of specific
storage technologies and application frameworks.

Different deployments may require different storage strategies:

- In-memory storage for development and testing.
- JSON snapshots for portable state persistence.
- SQLite for smaller standalone deployments.
- PostgreSQL for server-based deployments.
- Redis for optional caching and temporary state.
- API-backed repositories for remote access.

Large deployments must not require loading every stored
object into memory before analysis can begin.

## Decision

### 1. Domain models

Domain models remain framework-independent Python objects.

Existing dataclasses are retained unless a specific domain
requirement justifies changing them.

`netvoyager-network` must not depend on SQLAlchemy,
Pydantic, database drivers, or API frameworks.

Domain identity and technical state semantics remain
independent of persistence.

### 2. Storage package

Introduce `netvoyager-storage` as a separate package.

It will provide:

- Domain-oriented store contracts.
- Storage backend implementations.
- In-memory storage implementations.
- Data access and query operations.
- Optional cache integration.
- Storage-specific object conversion.

Existing stores are candidates for relocation into the
storage package.

Their interfaces and responsibilities must be reviewed
before migration.

Storage infrastructure must not introduce circular
dependencies between NetVoyager packages.

### 3. Analysis package

`netvoyager-analysis` consumes domain-oriented storage
contracts.

It must not depend directly on:

- SQLite or PostgreSQL drivers.
- SQLAlchemy ORM models.
- Redis clients.
- JSON or YAML persistence implementations.
- Pydantic API schemas.
- Web or API frameworks.

Identity validation, matching, reconciliation, policy
evaluation, and analysis rules remain the responsibility
of `netvoyager-analysis`.

### 4. Store behavior

Stores provide domain-oriented operations rather than
exposing a generic database interface.

Examples include:

- Retrieve a canonical device by ID.
- Find devices by serial number.
- Retrieve discovery candidates.
- Retrieve candidate resolutions.
- Retrieve evidence associated with an object.
- Query canonical prefixes and their relationships.

Store implementations must return and accept domain
objects according to their contracts.

Implementations may use indexes, lazy loading, queries,
or caching internally.

A complete baseline preload is optional, not mandatory.

### 5. Persistence implementations

In-memory stores remain supported.

File-based persistence may initially use versioned JSON
snapshots.

SQL persistence may use SQLAlchemy for SQLite and
PostgreSQL.

PostgreSQL repositories should support targeted queries
without loading complete datasets.

Redis may be used as a cache or temporary-state backend,
but is not automatically interchangeable with an
authoritative relational repository.

All implementations must preserve the same domain rules.

### 6. Model separation

Different layers may use different representations
of the same logical entity.

For a NetworkDevice:

- `NetworkDevice`: framework-independent domain model.
- `NetworkDeviceRecord`: optional SQLAlchemy mapping.
- `NetworkDeviceResponse`: optional Pydantic API schema.

SQL mappings belong outside domain packages.

API request and response schemas belong outside domain
packages.

Conversion between representations occurs at explicit
application or adapter boundaries.

ORM entities and API DTOs must not leak into analysis logic.

### 7. Transactions and consistency

Operations involving multiple related objects must
preserve consistency.

Database-backed implementations should use transactions
where required.

File-backed implementations must use safe, validated
state replacement.

Store contracts must define the necessary atomicity
and consistency guarantees.

### 8. Application orchestration

Applications select and configure storage implementations.

Analysis may operate against:

- Empty stores.
- Previously populated stores.
- Restored snapshots.
- Database-backed stores.
- Remotely provided domain objects.

The analysis package must not need to know the physical
location of the stored data.

## Consequences

- Domain models remain portable and independently testable.
- Analysis behavior can be tested using in-memory stores.
- SQLite and PostgreSQL may share SQL repository logic.
- Large datasets can be queried without full preloading.
- Different backends can be introduced incrementally.
- Storage migration does not require changing domain identity.
- Existing store behavior must be preserved during relocation.
- Domain rules must not be duplicated across storage adapters.

## Implementation Notes

This ADR establishes architectural boundaries.

It does not require immediate implementation of all
storage adapters or migration of existing stores.

Begin with the current store contracts and migrate
incrementally with regression tests.

## Related Decisions

- ADR-0001 — Domain model simplicity
- ADR-0006 — UUIDv5 identity and state
- ADR-0007 — Repeatable discovery
- ADR-0008 — Identity and inventory
- ADR-0009 — Device discovery and reconciliation
- ADR-0010 — Repeated import evidence
