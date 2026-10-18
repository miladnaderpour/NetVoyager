
# ADR-0013 — Manual and Batch Device Identity Approval

## Status

Accepted

## Date

2026-10-18

## Context

Automatic discovery cannot always establish physical device
identity with sufficient certainty.

Candidate observations may share management IP addresses,
hostnames, or other attributes without having sufficient
strong evidence for automatic reconciliation.

NetVoyager must support explicit human identity decisions
and the import of previously verified device inventories.

These operations must reuse the existing identity validation,
policy authorization, reconciliation, and evidence architecture.

## Decision

### 1. Identity approval methods

NetVoyager supports three identity reconciliation methods:

- Automatic reconciliation using trusted identity evidence.
- Manual confirmation or rejection by authorized engineers.
- Batch approval using an authorized inventory or approval list.

All methods use the same canonical identity and
reconciliation rules.

### 2. Manual approval

Authorized engineers may review supporting observations
and confirm or reject proposed identity relationships.

Manual approval must:

- Identify the affected candidates or canonical devices.
- Preserve supporting evidence and original observations.
- Record the approving identity and decision context.
- Respect existing confirmed or rejected relationships.
- Require explicit authorization.
- Preserve decision history for subsequent discovery runs.

Confirming a candidate relationship does not automatically
require canonical promotion.

Candidate relationship status and candidate lifecycle
remain independent.

### 3. Batch approval

NetVoyager supports importing approved device inventories
to authorize multiple canonical promotions or candidate
resolutions.

Batch input may reference:

- Existing candidate IDs.
- Existing canonical device IDs.
- Physical serial numbers with approved canonical names.

Serial-based selection must use the existing identity
validation rules and must resolve ambiguity before approval
can be applied.

Multiple candidates may resolve to one canonical device
when the approved identity evidence supports that decision.

### 4. Authorization

Importing a file does not automatically establish approval.

Approval authority must come from an authenticated and
authorized operator or trusted approval source.

The PolicyEngine remains responsible for authorization.

Approval provenance must be recorded independently
of ordinary source observations.

### 5. Validation and conflict handling

Before applying approvals, NetVoyager must validate:

- Candidate and canonical device existence.
- Duplicate or contradictory assignments.
- Existing candidate resolutions.
- Serial conflicts and ambiguous matches.
- Canonical naming and identity collisions.
- Previously rejected relationships.
- Relevant hardware replacement and rename requirements.
- Required source and action permissions.

Conflicts must not be bypassed silently.

### 6. Preview and execution

Batch approval must support a dry-run validation plan.

The plan identifies:

- Canonical devices to create.
- Existing canonical devices to reuse.
- Candidates to resolve.
- Relationships to confirm or reject.
- Unchanged records.
- Blocked or conflicting actions.

Approval execution must use the existing reconciliation
services rather than duplicate identity rules.

The initial batch execution contract should provide
all-or-nothing consistency for the approved batch.

### 7. Repeatability and audit

Repeated execution of an unchanged approved batch must
not generate duplicate canonical devices, resolutions,
or approval decisions.

Every applied approval must retain:

- Approval or batch identity.
- Authorized actor or trusted source.
- Decision and execution outcome.
- Supporting evidence references.
- Affected candidate and canonical identities.
- Relevant timestamps and audit context.

Original discovery evidence must remain preserved.

### 8. Storage independence

Manual and batch approval services consume domain-oriented
store protocols.

They must not depend on a particular database, ORM,
file format, or cache implementation.

Approval history and decisions must remain available
across subsequent discovery runs.

## Consequences

- Weak matches can be resolved through authorized review.
- Verified inventories can establish canonical devices
  without requiring individual manual approvals.
- Batch input does not override identity safety checks.
- Candidate and canonical identities remain independently
  traceable.
- Approval workflows are compatible with memory, file,
  and database-backed storage.
- UI implementation is not required before core approval
  functionality can be tested.

## Related Decisions

- ADR-0006 — UUIDv5 identity and state
- ADR-0008 — Identity and inventory
- ADR-0009 — Device discovery and reconciliation
- ADR-0011 — Storage architecture and model separation
- ADR-0012 — Device renaming and hardware replacement
