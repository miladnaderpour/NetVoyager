
# ADR-0016 — Hybrid Domain Models and SQLAlchemy-Native Intelligence

## Status

Accepted

## Date

2026-10-19

## Context

NetVoyager has evolved from in-memory network analysis toward
persistent, evidence-driven discovery and reconciliation.

The platform must support relational queries, transactional
operations, evidence history, and repeatable collection runs.

Maintaining both intelligence dataclasses and separate ORM
entities introduces unnecessary duplication for records whose
primary lifecycle is database-backed.

Network-domain models have different requirements. They must
remain reusable independently of SQLAlchemy, database connections,
and application infrastructure.

## Decision

### 1. Hybrid model architecture

NetVoyager adopts the following model strategy:

- `netvoyager-network` retains framework-independent dataclasses.
- `netvoyager-intelligence` owns SQLAlchemy-native evidence,
  relation, and finding models.
- `netvoyager-analysis` consumes shared network and intelligence
  models without importing `netvoyager-database`.
- `netvoyager-database` owns database engines, sessions,
  SQL repositories, transactions, and schema migrations.
- `netvoyager-core` provides shared logging, exceptions, and
  foundational utilities.

No separate ORM entity is required for an intelligence model
that is already mapped directly through SQLAlchemy.

### 2. Database-backed operation

Database-backed storage is the default for operational state.

Supported initial configurations include:

- SQLite in-memory for development and testing.
- SQLite file databases for local persistent operation.
- PostgreSQL for server-based operation.

SQLite in-memory is transactional but does not provide
persistence across database lifecycles.

In-memory application stores may remain temporarily during
migration but are not the primary persistence architecture.

### 3. Package dependencies

Both Analysis and Database may depend on Intelligence.

Analysis and Database must not import each other.

Intelligence may depend on SQLAlchemy, but must not depend
on Database for its model definitions.

Database infrastructure must not leak into network-domain models.

### 4. Evidence persistence

EvidenceRecord and EvidenceRelation are SQLAlchemy-native models.

One EvidenceRecord may have multiple EvidenceRelation rows.

Each relation references one domain object through:

- object_id: UUID
- object_type: str

The database enforces the EvidenceRecord foreign key.

Object references are polymorphic and are not constrained to
one domain-object table.

The composite relation primary key is:

    (evidence_id, object_id)

An index on object_id supports reverse evidence lookup.

Object types serve as an additional safeguard and must not
conflict for the same object identity.

### 5. Evidence preservation

The migration must preserve:

- Source provenance.
- Original observation records.
- Record identities and timestamps.
- Native Python evidence details through explicit serialization.
- Multiple observations across repeated discovery runs.
- Existing evidence relationships.
- Efficient reverse lookup by object UUID.
- Non-destructive historical evidence.

Evidence relationships must not replace operational candidate,
device, prefix, or site relationships.

### 6. Repository and transaction boundaries

Repositories persist and retrieve authorized state.

They do not perform identity matching, policy authorization,
candidate reconciliation, or canonical promotion.

Database sessions and transactions are controlled through
the existing Unit of Work pattern.

Repositories must not independently commit operations that
belong to a shared transaction.

### 7. Migration strategy

Migration is incremental:

1. Establish shared SQLAlchemy metadata and mapping ownership.
2. Implement SQLAlchemy-native EvidenceRecord.
3. Implement SQLAlchemy-native EvidenceRelation.
4. Preserve evidence APIs and replace in-memory persistence.
5. Integrate SQL repositories and Unit of Work.
6. Migrate findings and additional intelligence records.
7. Remove obsolete compatibility code after validation.

Existing stored evidence must not be silently discarded.

### 8. Relationship to earlier ADRs

This ADR supersedes ADR-0011 where it requires framework-
independent intelligence models or separate ORM representations.

ADR-0011 remains authoritative for independent network-domain
models, repositories, Unit of Work, and transaction behavior.

This ADR resolves the intelligence persistence choice deferred
in ADR-0014.

ADR-0015 remains authoritative for retirement of the Storage
package and relocation of its contracts and exceptions.

All established identity, discovery, provenance, and
reconciliation rules remain in effect.

## Consequences

### Benefits

- One model representation for intelligence records.
- Reduced mapping boilerplate.
- Relational persistence and indexed evidence retrieval.
- Consistent transaction management.
- Independent network-domain models.
- Clear package ownership.

### Trade-offs

- Intelligence requires SQLAlchemy.
- Analysis indirectly depends on SQLAlchemy.
- Frozen/slotted evidence dataclasses require migration.
- Existing in-memory stores must be adapted or retired.
- Native evidence details require explicit serialization.
- SQLAlchemy metadata must be shared consistently.

## Implementation status

Architecture accepted.

Model and repository migration pending.
