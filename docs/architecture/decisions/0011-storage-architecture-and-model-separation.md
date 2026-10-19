
# ADR-0011 — Storage Architecture and Model Separation

## Status

Accepted

## Date

2026-10-18

## Clarification

The [Intelligence extraction addendum](#addendum-intelligence-package-extraction-2026-10-18)
and [ADR-0014](0014-intelligence-package-boundary.md) clarify evidence/finding
ownership. Other decisions below remain in force unless explicitly superseded.

[ADR-0015](0015-retire-storage-package.md) subsequently retires Storage, moves
its Protocols to Analysis and its exceptions to Database, and supersedes the
Storage package requirements and temporary migration notes below.

[ADR-0015](0015-retire-storage-package.md) subsequently retires Storage, moves
its Protocols to Analysis and its exceptions to Database, and supersedes the
Storage package requirements and temporary migration notes below.

## Context

NetVoyager is evolving into a modular network discovery,
analysis, inventory, and automation platform.

The platform will eventually support API, CLI, worker,
scheduler, and web applications.

NetVoyager must support different storage implementations
without coupling domain models or analysis services to a
specific persistence technology.

Different deployments may require different strategies:

- In-memory repositories for lightweight operations and tests.
- JSON snapshots for portable state persistence.
- SQLite in-memory for transactional development and testing.
- SQLite files for smaller standalone deployments.
- PostgreSQL for server-based deployments.
- Redis for optional caching and temporary state.
- API-backed repositories for remote data access.

Large deployments must not require loading all stored
objects into memory before analysis can begin.

The existing analysis package contains in-memory stores
that combine data access with some lifecycle operations.

These responsibilities must be separated without changing
established identity, reconciliation, evidence, or policy
behavior.

## Decision

### 1. Domain models

Domain models remain framework-independent Python objects.

Existing dataclasses are retained unless a specific domain
requirement justifies changing them.

`netvoyager-network` must not depend directly on:

- SQLAlchemy.
- Pydantic.
- Database drivers.
- Database sessions.
- API frameworks.

Domain identity and technical state remain independent
of persistence.

Existing UUIDv5 identity and technical-state semantics
must remain unchanged unless explicitly amended by
another accepted ADR.

### 2. Repository Pattern

NetVoyager adopts the Repository Pattern for domain-oriented
data retrieval and persistence.

Repositories provide operations such as:

- Retrieve a canonical device by ID.
- Find devices by serial number.
- Find devices by management IP.
- Find devices by asset tag.
- Retrieve discovery candidates.
- Retrieve candidate relationships.
- Retrieve candidate resolutions.
- Retrieve evidence associated with an object.
- Persist already-authorized changes.

Repository interfaces must not expose SQL expressions,
ORM entities, sessions, database connections, or API DTOs.

Repository operations accept and return domain objects.

Repositories must not perform identity validation,
policy authorization, or reconciliation decisions.

### 3. Repository naming conventions

The term `Repository` is used for storage-independent
data-access contracts and their implementations.

Examples:

- `NetworkDeviceRepositoryProtocol`
- `DeviceDiscoveryRepositoryProtocol`
- `EvidenceRepositoryProtocol`
- `AttributeAssertionRepositoryProtocol`
- `NetworkPrefixRepositoryProtocol`

Concrete SQL implementations use the `Sql` prefix.

Example:

- `SqlNetworkDeviceRepository`

The term `Store` is reserved for components that genuinely
manage in-memory collections, caches, or specialized
internal state.

Existing store implementations may be migrated
incrementally while preserving established behavior.

### 4. Repository protocols

Repository contracts use Python `typing.Protocol`
and structural typing.

Concrete implementations do not need to inherit
from their protocols.

Analysis services depend on repository contracts
rather than concrete implementations.

The following principles apply:

- Protocols define operations required by consumers.
- In-memory implementations may satisfy protocols.
- SQL repositories may satisfy the same contracts.
- Test fakes and mocks may satisfy protocols.
- Repository interfaces remain domain-oriented.
- Repository interfaces remain storage-independent.
- Queries support targeted retrieval.
- Complete dataset preloading is not mandatory.
- Queries must preserve potentially ambiguous results.

Identity lookups must not arbitrarily select a single
record when multiple objects match the search criteria.

A repository retrieves potential matches.

Identity validation and reconciliation determine
what those matches mean.

### 5. Repository responsibilities

Repositories are responsible for:

- Retrieving domain objects.
- Persisting domain objects.
- Querying stored relationships.
- Maintaining persistence indexes.
- Enforcing structural storage constraints.
- Reporting storage failures.
- Participating in Unit of Work transactions.

Repositories are not responsible for:

- Establishing physical identity.
- Evaluating source trust.
- Authorizing canonical promotion.
- Deciding candidate lifecycle transitions.
- Confirming or rejecting identity relationships.
- Deciding hardware replacement.
- Deciding canonical renaming.
- Generating reconciliation conclusions.

For device discovery, the repository persists and retrieves:

- DeviceDiscoveryCandidate.
- DeviceDiscoveryCandidateRelationship.
- Candidate resolution state.
- DeviceDiscoveryDecision.

The discovery repository does not execute the
domain operation `resolve_candidate()`.

That operation belongs to DeviceReconciliationService.

Repository methods persist the resulting authorized
state and associated decision records.

### 6. Unit of Work Pattern

NetVoyager adopts an application-level Unit of Work Pattern.

Unit of Work contracts use Python `typing.Protocol`.

The Unit of Work coordinates repositories participating
in one consistent transaction boundary.

Its responsibilities include:

- Opening a transaction scope.
- Providing participating repositories.
- Coordinating consistent reads and writes.
- Committing changes explicitly.
- Rolling back uncommitted changes.
- Preserving transaction consistency.
- Handling transaction failures.

A Unit of Work must not make identity or policy decisions.

Application services determine which operations should
be executed.

The initial Unit of Work supports device reconciliation.

The same abstraction may later coordinate repositories
for evidence, attributes, IPAM, findings, and other
application workflows.

Transaction scope must include all records required
for consistency within the operation.

### 7. Transaction semantics

Unit of Work implementations use explicit commit
and rollback operations.

The following rules apply:

- Changes require an explicit commit.
- Uncommitted changes are rolled back when a scope exits.
- Exceptions before commit cause rollback.
- A failed commit must not leave partially committed state.
- Repositories participating in one transaction must share
  the same consistency boundary.
- Transaction failures use NetVoyager exception conventions.

A transaction is not automatically atomic across
independent databases, Redis, or remote APIs.

Distributed consistency requirements must be handled
explicitly if introduced later.

### 8. Storage package

`netvoyager-storage` owns storage-independent
repository contracts and Unit of Work contracts.

It may provide:

- Repository protocols.
- UnitOfWorkProtocol.
- Lightweight shared storage contracts.
- Storage-specific exception types.
- Optional in-memory or cache implementations.
- Shared contract testing utilities.

It must not depend on a particular SQL ORM or database
driver merely to expose its contracts.

It must not depend on netvoyager-analysis.

Existing in-memory store responsibilities may be
relocated incrementally.

Business logic currently implemented inside stores
must be moved to the appropriate analysis services.

### 9. Database package

Introduce `netvoyager-database` as a separate package.

It owns SQL-specific persistence infrastructure:

- SQLAlchemy ORM entities.
- SQL repository implementations.
- Domain-to-ORM mapping.
- ORM-to-domain mapping.
- Database engine configuration.
- Session factories.
- SQL transaction management.
- SQL Unit of Work implementations.
- Database schema definitions and migrations.

`netvoyager-database` implements contracts defined
by `netvoyager-storage`.

It must not depend on netvoyager-analysis.

Database implementations must not duplicate identity,
reconciliation, or policy business rules.

### 10. SQLAlchemy

SQLAlchemy 2.x is the selected SQL persistence framework.

Database ORM models use SQLAlchemy 2.x declarative
mapping conventions.

SQLAlchemy models remain separate from domain dataclasses.

ORM entities may contain additional persistence-specific
attributes, including:

- Database creation timestamps.
- Database modification timestamps.
- Record revision numbers.
- Persistence metadata.
- Relationship and foreign-key mappings.

Persistence-specific attributes must not automatically
become domain attributes.

A database revision is separate from the domain
technical-state identifier.

SQLAlchemy sessions and ORM entities must not leak
into analysis services.

### 11. ORM naming conventions

SQLAlchemy persistence classes use the `Entity` suffix.

Examples:

- `NetworkDeviceEntity`
- `DeviceDiscoveryCandidateEntity`
- `DeviceDiscoveryCandidateRelationshipEntity`
- `DeviceDiscoveryDecisionEntity`

Framework-independent domain classes retain their
existing names without an ORM suffix.

Examples:

- `NetworkDevice`
- `DeviceDiscoveryCandidate`
- `DeviceDiscoveryCandidateRelationship`
- `DeviceDiscoveryDecision`

Repository implementations return domain objects,
not SQLAlchemy entities.

The `Record` suffix is not the default convention
for ORM models.

### 12. Model separation and conversion

NetVoyager separates domain models, database entities,
and API contracts.

For a canonical network device:

- `NetworkDevice`: domain model.
- `NetworkDeviceEntity`: SQLAlchemy persistence model.
- `NetworkDeviceResponse`: API response schema.

API request schemas may be defined separately.

Examples:

- `NetworkDeviceCreateRequest`
- `NetworkDeviceUpdateRequest`

API schemas belong outside domain and database packages.

Conversion between representations occurs at explicit
application or adapter boundaries.

Database mappers must preserve established domain identity
and technical-state behavior.

Stored domain identity must be validated during
reconstruction rather than silently replaced.

### 13. Database backends

The initial SQL implementation uses SQLite in-memory.

SQLite in-memory provides:

- SQL query execution.
- Indexes and constraints.
- Transactions.
- Commit and rollback.
- Integration testing without persistent database files.

The initial SQL repositories and Unit of Work must be
designed for reuse with SQLite-file and PostgreSQL.

The shared SQLAlchemy implementation must avoid
unnecessary SQLite-specific assumptions.

Backend-specific connection management, isolation,
concurrency, and performance requirements may differ.

SQLite in-memory database lifetime must be managed
through appropriate engine and connection configuration.

### 14. Database schema evolution

Database schema evolution is expected.

Additional ORM entities, columns, indexes, constraints,
and relationships may be introduced as NetVoyager grows.

Only models required by current workflows need to be
implemented initially.

The first SQL implementation focuses on:

- Canonical NetworkDevice.
- Device discovery candidates.
- Candidate relationships.
- Discovery decisions.
- Required reconciliation persistence.

Additional domains will be mapped incrementally.

Alembic is the selected migration mechanism for
persistent SQL database schemas.

In-memory integration tests may initialize schemas
directly from SQLAlchemy metadata.

Persistent deployments should use managed schema
migrations rather than recreating databases.

### 15. Source authority and identity validation

The PolicyEngine remains responsible for source-,
method-, claim-, and action-specific authorization.

DeviceMatchingRules remains responsible for
source-specific comparison behavior.

IdentityValidator remains responsible for evaluating
physical identity evidence and ambiguity.

Repositories retrieve possible matches without
deciding whether the identities are equivalent.

A management-IP match may indicate a possible
relationship but cannot independently confirm
physical identity.

Multiple matching candidates must remain independently
retrievable.

Source-specific serial matching rules must not be
bypassed by overly restrictive repository queries.

### 16. Application orchestration

Applications select and configure concrete repository
and Unit of Work implementations.

Applications may include:

- API services.
- CLI commands.
- Workers.
- Schedulers.
- Other orchestration entry points.

The analysis package receives repository or Unit of Work
contracts through dependency injection.

The analysis package must not know whether objects
originate from SQLite, PostgreSQL, in-memory state,
file-based storage, or an external service.

Backend selection belongs to application composition.

### 17. Shared infrastructure

All NetVoyager infrastructure packages reuse the
shared conventions provided by `netvoyager-core`.

This includes:

- Structured logging.
- Centralized exception handling.
- Shared value types.
- Consistent error codes and details.

Packages use `get_logger()` for logging.

Application entry points configure logging through
`setup_logging()`.

Exceptions inherit from the appropriate NetVoyager
core exception types.

Exception objects do not log themselves.

Callers determine how failures should be handled
and logged.

Storage implementations must not introduce competing
logging or exception frameworks.

### 18. Dependency boundaries

The dependency direction is:

- netvoyager-analysis -> netvoyager-storage
- netvoyager-analysis -> netvoyager-network
- netvoyager-storage -> netvoyager-network
- netvoyager-storage -> netvoyager-core
- netvoyager-database -> netvoyager-storage
- netvoyager-database -> netvoyager-network
- netvoyager-database -> netvoyager-core

The following dependencies are forbidden:

- netvoyager-network -> netvoyager-storage
- netvoyager-network -> netvoyager-database
- netvoyager-analysis -> netvoyager-database
- netvoyager-storage -> netvoyager-database
- netvoyager-storage -> netvoyager-analysis
- netvoyager-database -> netvoyager-analysis

Concrete implementations are selected and injected
at application startup.

Circular package dependencies must be avoided.

### 19. Testing strategy

Repository protocols define structural interfaces.

Protocol conformance alone does not guarantee
behavioral equivalence.

Shared repository contract tests must validate
compatible implementations.

Tests should cover:

- Object creation and retrieval.
- Exact identity lookups.
- Ambiguous lookup results.
- Duplicate handling.
- Missing objects.
- Referential integrity.
- Domain reconstruction.
- Transaction commit and rollback.
- Consistency after failed operations.

Analysis unit tests may use lightweight fake repositories.

SQL transaction integration tests use SQLite in-memory.

Backend-specific concurrency and isolation behavior
requires additional tests.

Tests must preserve existing NetVoyager identity,
reconciliation, policy, and evidence behavior.

## Consequences

- Domain models remain independent of SQLAlchemy and APIs.
- Repository interfaces remain storage-independent.
- Analysis services consume Protocol contracts.
- Database mappings are maintained separately.
- ORM entities can evolve without changing domain identity.
- Repository and Unit of Work implementations can be tested
  independently of analysis.
- SQLite and PostgreSQL may share SQLAlchemy mappings
  and repository implementations.
- Large datasets can be queried without full preloading.
- Canonical identity and technical state remain unchanged.
- Transaction consistency is handled explicitly.
- Business rules are not duplicated across storage adapters.
- Existing stores can be migrated incrementally.
- Additional database schema changes are expected and supported.
- Storage implementation complexity increases due to explicit
  domain-to-ORM conversion and separate persistence classes.

## Implementation Notes

This ADR establishes the accepted architecture.

Implementation proceeds incrementally.

The initial implementation sequence is:

1. Create netvoyager-database package.
2. Configure SQLAlchemy 2.x dependencies.
3. Establish declarative base and metadata conventions.
4. Implement SQLite in-memory engine and session factory.
5. Define NetworkDeviceEntity.
6. Implement domain-to-ORM and ORM-to-domain mapping.
7. Implement SqlNetworkDeviceRepository.
8. Define discovery-related ORM entities and repositories.
9. Implement SqlUnitOfWork with explicit commit and rollback.
10. Add repository contract and SQL integration tests.
11. Migrate reconciliation services to repository and
    Unit of Work contracts.
12. Extend persistence to evidence, attributes, and other
    domains as required.

Do not introduce database-specific behavior into domain
models or analysis services.

Do not change existing UUIDv5 identity or technical-state
calculations as part of this storage refactor.

## Related Decisions

- ADR-0001 — Domain model simplicity
- ADR-0006 — UUIDv5 identity and state
- ADR-0007 — Repeatable discovery
- ADR-0008 — Identity and inventory
- ADR-0009 — Device discovery and reconciliation
- ADR-0010 — Repeated import evidence
- ADR-0012 — Canonical device renaming and hardware replacement
- ADR-0013 — Manual and batch device identity approval

## Addendum: Intelligence Package Extraction (2026-10-18)

### Status

Accepted clarification; Intelligence persistence strategy remains open.

### Ownership

[ADR-0014](0014-intelligence-package-boundary.md) establishes
`netvoyager-intelligence` as the owner of evidence and findings models and
their associated store behavior. They must not move into `netvoyager-network`
to satisfy persistence imports. This supersedes any conflicting ownership
assumptions in this ADR without rewriting its historical storage decision.

### Unchanged and deferred decisions

Network domain models remain independent of SQLAlchemy. The initial Intelligence
extraction preserves model and store behavior, including existing exceptions.
Core logging and exception conventions continue to apply to new work; changing
existing exception contracts requires an explicit, separately reviewed change.

Retiring `netvoyager-storage`, replacing its Protocol structure, permitting
concrete Database imports in Analysis, and adopting ORM-native Intelligence
models remain undecided. Discussion of these options does not revoke the
existing dependency boundaries or authorize a migration.

### Follow-up: Repository Protocol relocation (2026-10-18)

The approved first step toward simplifying Storage moves
`NetworkDeviceRepositoryProtocol` and `DeviceDiscoveryRepositoryProtocol`
unchanged into `netvoyager_analysis.protocols`. Storage's remaining
`UnitOfWorkProtocol` imports them there, so Storage temporarily depends on
Analysis. This narrowly supersedes the Storage-to-Analysis prohibition above.

The approved follow-up also moves `UnitOfWorkProtocol` unchanged into
`netvoyager_analysis.protocols.unit_of_work`, alongside the repository
contracts. Storage no longer needs the temporary Analysis dependency.
Storage exceptions remain in place for now; removing the package is subsequent
work. These moves do not introduce concrete Database imports in Analysis or
change persistence behavior.

If those boundaries change, a separate superseding ADR must identify actual
imports and package dependencies, the migration steps, rollback strategy, and
required tests. Package extraction alone does not decide persistence strategy.

## Addendum — Hybrid Intelligence Persistence (2026-10-19)

ADR-0016 introduces SQLAlchemy-native intelligence models.

The framework-independent domain-model requirement continues
to apply to `netvoyager-network`.

Evidence and findings owned by `netvoyager-intelligence`
are an explicit exception to the original general model
separation policy.

These intelligence models do not require corresponding
duplicate ORM entities in `netvoyager-database`.

Database remains responsible for sessions, repositories,
transactions, engines, and migrations.

Analysis and Database remain independent of each other.

All repository, Unit of Work, identity, transaction,
and network-domain separation rules remain unchanged.

ADR-0015 continues to supersede the retired Storage
package provisions.
