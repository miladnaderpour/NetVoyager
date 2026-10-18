# ADR-0015 — Retire the Storage Package

## Status

Accepted

## Date

2026-10-18

## Context

Storage contained three repository/transaction Protocols and shared persistence
exceptions. The repository and Unit of Work Protocols have moved unchanged to
Analysis. Database is the only implementation package using the exceptions.
Keeping a separate distribution for these exceptions is unnecessary.

## Decision

- Analysis owns `NetworkDeviceRepositoryProtocol`,
  `DeviceDiscoveryRepositoryProtocol`, and `UnitOfWorkProtocol` under
  `netvoyager_analysis.protocols`. Their interfaces remain unchanged.
- Database owns persistence exceptions in `netvoyager_database.exceptions`.
  Preserve class names, Core inheritance, error codes, messages, and details.
  Exceptions do not log themselves; callers use Core logging conventions.
- Update Database implementations and tests to import these exceptions from
  Database, remove its Storage dependency, and retire the Storage distribution.
- Do not introduce Database-to-Analysis imports merely to inherit Protocols;
  structural typing does not require implementation inheritance.
- This decision does not introduce concrete Database imports in Analysis or
  select an Intelligence persistence representation.

## Consequences and migration

Old Storage import paths are removed. External consumers must update Protocol
imports to Analysis and exception imports to Database. No compatibility package
is retained. There are no schema or data migrations and no changes to domain
identity, reconciliation, or transaction behavior.

Validate relocated Protocol imports and run the full Database suite, including
repository conflict/missing-object and transaction failure tests. Check source
imports and package metadata for remaining Storage dependencies. Rollback must
restore the Storage distribution, consumer imports, and dependency metadata
together.

## Related decisions

This supersedes the Storage package ownership and dependency requirements in
[ADR-0011](0011-storage-architecture-and-model-separation.md), including its
temporary migration notes, and resolves the Storage retention question in
[ADR-0014](0014-intelligence-package-boundary.md). Other decisions remain in force.
