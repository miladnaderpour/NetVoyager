
# ADR-0012 — Canonical Device Renaming and Hardware Replacement

## Status

Accepted

## Date

2026-10-18

## Context

NetVoyager uses deterministic UUIDv5 identities for
canonical NetworkDevice objects.

The current identity is derived from the canonical
device name.

This supports repeatable discovery: the same canonical
identity inputs generate the same device ID across runs.

However, two lifecycle operations require special handling:

1. Renaming a device according to a new naming SOP.
2. Replacing device hardware through RMA or planned change.

These operations must preserve appropriate relationships,
evidence, and reconciliation history without accidentally
creating duplicate canonical devices.

## Decision

### 1. Canonical identity

Retain the existing NetworkDevice identity strategy:

- `device_id` is UUIDv5 derived from canonical name.
- UUIDv5 namespaces and canonicalization rules remain fixed.
- Identical canonical identity inputs produce identical IDs.
- `state_id` remains separate from canonical identity.
- Serial number remains a technical state attribute,
  not the canonical identity key.

Do not replace the current identity strategy with UUIDv4.

### 2. Device renaming

Canonical device renaming is an explicit, authorized
identity migration.

It must not occur automatically because a discovery
source reports a different hostname or device name.

An approved rename must:

1. Validate the new canonical name.
2. Check for existing identity and naming conflicts.
3. Generate the new deterministic UUIDv5 device ID.
4. Migrate dependent operational references.
5. Rebuild affected indexes and derived identifiers.
6. Preserve original observations and historical evidence.
7. Validate referential integrity.
8. Commit the migration consistently.

The migration scope includes relevant:

- Candidate-to-device resolutions.
- Device relationships.
- Evidence links.
- Attribute assertions.
- Findings.
- Site and network associations.
- Other references containing the canonical device ID.

Historical source observations must not be rewritten to
pretend that a device always had its new name.

A rename must not leave dangling references.

### 3. No mandatory name-alias registry

A separate legacy-name alias registry is not required
for ordinary device reconciliation.

A previously renamed device should be rediscovered
through existing identity validation and reconciliation.

A trusted physical serial match can identify an existing
canonical device despite differences in observed names.

Source-specific serial comparison rules remain effective.

Hostname or management IP alone cannot confirm physical
identity.

A canonical ID must not be created from an observed name
before the normal reconciliation requirements are evaluated.

### 4. Hardware replacement

An RMA or planned physical hardware replacement is an
explicitly authorized lifecycle operation.

The replacement must be registered and approved before
discovery processes the replacement hardware.

The replacement process must associate:

- Existing canonical device identity.
- Previous physical serial number.
- Replacement physical serial number.
- Authorized replacement decision.
- Relevant evidence and change context.

Approval authorizes continuity of the existing canonical
inventory identity despite the physical hardware change.

### 5. Identity behavior during replacement

An approved replacement preserves:

- Canonical name.
- Canonical device ID.
- Existing applicable operational relationships.
- Original source observations.
- Historical reconciliation and replacement evidence.

The current serial number and affected technical attributes
are updated through the authorized replacement workflow.

Technical state is recalculated where applicable.

An RMA does not require generating a new canonical device ID
when the canonical name remains unchanged.

### 6. Unregistered hardware changes

If a previously unknown serial is discovered without an
approved replacement:

- Do not automatically overwrite an existing serial.
- Do not infer replacement based only on hostname or IP.
- Evaluate the observation through normal identity validation.
- Preserve ambiguous observations as discovery candidates.
- Report an identity conflict when appropriate.
- Permit new canonical creation only when strong,
  unambiguous identity and source policy authorize it.

Different serial numbers must not automatically establish
continuity with an existing canonical device.

An unregistered replacement may therefore be discovered
as a different device.

The system must not silently merge it with the old device.

### 7. Reconciliation

Normal discovery attempts to find existing canonical
devices before creating new ones.

A trusted, unambiguous serial correspondence can support
reuse of an existing canonical identity.

Candidate resolution remains evidence-backed and subject
to policy authorization.

Existing rejected relationships and contradictory identity
evidence must be respected.

### 8. Evidence and auditability

Preserve original evidence records and source observations.

Approved renames and hardware replacements must have
auditable authorization and outcome records.

Historical serial numbers must remain accessible as
historical facts, without automatically acting as current
serial identifiers.

EvidenceStore remains responsible for provenance, not
operational identity matching.

### 9. Consistency

Rename and replacement operations must preserve
referential integrity.

Database implementations must support appropriate
transaction boundaries.

File implementations must validate and safely replace
the resulting state.

Partial identity migrations must not be committed.

## Consequences

- Deterministic device identities remain supported.
- SOP renaming requires controlled reference migration.
- Existing matching and reconciliation remain responsible
  for recognizing previously renamed devices.
- Ordinary imports cannot silently perform hardware RMA.
- Hardware replacement requires authorization before
  normal discovery is run against replacement hardware.
- Canonical identity and physical hardware state remain
  distinct concepts.
- No additional name-alias system is mandatory.
- No comprehensive event-sourcing system is required.
- Rename and replacement implementations remain future work.

## Related Decisions

- ADR-0006 — UUIDv5 identity and state
- ADR-0007 — Repeatable discovery
- ADR-0008 — Identity and inventory
- ADR-0009 — Evidence-driven reconciliation
- ADR-0011 — Storage architecture and model separation
