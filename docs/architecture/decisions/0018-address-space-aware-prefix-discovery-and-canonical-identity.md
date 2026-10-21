
# ADR-0018 — Address-Space-Aware Prefix Discovery and Canonical Identity

## Status

Accepted

## Date

2026-10-21

## Scope

Network prefix discovery, address-space identity, canonical prefix
management, reconciliation, relationships, and persistence.

## Context

NetVoyager collects network addressing information from heterogeneous
sources, including BGP routing tables, interface configurations,
static routes, DHCP configurations, inventories, and external systems.

The existing IPAM implementation normalizes prefixes and creates
canonical NetworkPrefix objects during analysis.

However, NetVoyager now requires a governed discovery lifecycle
that separates observed information from accepted canonical inventory.

The existing Device Discovery architecture establishes a suitable
pattern:

- Source observations are preserved independently.
- Discovery candidates have their own identities.
- Candidates can be correlated without destructive merging.
- Canonical identity is established through reconciliation.
- Promotion and resolution follow authorization policies.
- Evidence, relationships, and decisions remain traceable.

Network prefixes require the same principles, with prefix-specific
matching and validation policies.

Additionally, identical CIDRs may exist in independent address
spaces. Therefore, CIDR alone is insufficient for canonical identity.

NetVoyager's persistent IPAM implementation is greenfield.
Previous prefix-processing results were transient and were not
persisted as canonical database records.

Consequently, no existing persistent NetworkPrefix identities
require data migration or backward-compatibility mappings.

## Decision

### 1. Prefix Discovery Architecture

NetVoyager shall use three distinct stages:

1. PrefixObservation
2. PrefixDiscoveryCandidate
3. NetworkPrefix

Each stage has its own responsibility, identity, and lifecycle.

The general discovery and reconciliation principles established
for devices shall be reused.

Prefix-specific matching and validation rules remain independent.

### 2. PrefixObservation

PrefixObservation represents information collected from a source.

Examples include:

- BGP advertisements and locally originated routes.
- Static routing entries.
- Connected interface networks.
- DHCP scopes.
- Documented address allocations.
- External inventory information.

Each observation preserves the information actually reported
by its source.

Relevant properties may include:

- Source and SourceDataset references.
- Observed CIDR or address information.
- Observed routing context.
- Collection timestamp.
- Source-local identifiers.
- Observation-specific attributes.
- Collection completeness and validity.
- Provenance references.

Source observations belong to netvoyager-analysis.

Observations are not canonical NetworkPrefix objects.

Repeated observations must not be destructively collapsed.

A source may report an existing prefix without proving that
the prefix is active, allocated, reachable, or correctly owned.

Absence of a prefix from a collection does not automatically
prove that the prefix has been removed.

### 3. AddressSpace

Introduce AddressSpace as a first-class domain concept.

An AddressSpace represents an independent namespace for
network address identity.

AddressSpace is distinct from:

- VRF.
- NetworkScope.
- Site.
- Tenant.
- VLAN.
- Routing protocol instance.

An AddressSpace may be related to these concepts through
explicit relationships.

#### Identity

AddressSpace shall have a stable UUID identity.

Its canonical identity must not depend on mutable display
attributes.

Canonical naming shall be unique within the applicable
AddressSpace registry.

Changing a display name must not silently change the
AddressSpace identity.

The exact identity generation and naming rules shall be
implemented and tested in the AddressSpace domain milestone.

#### Default AddressSpace

NetVoyager shall provide a default AddressSpace named:

    global

Its UUID shall be deterministic and stable.

The same default AddressSpace shall be used consistently
across database instances and repeated processing.

The default AddressSpace supports ordinary managed prefixes
without requiring a separate routing namespace.

However, an observation with an unknown or unresolved
AddressSpace shall not automatically be assigned to global.

Source configuration, validated routing context, or an
authorized reconciliation policy must establish the
appropriate AddressSpace.

#### Address Families

AddressSpace shall support both IPv4 and IPv6 prefix identities.

The canonical prefix includes its address family.

The model must not assume that only IPv4 exists.

### 4. Canonical NetworkPrefix Identity

NetworkPrefix represents an accepted canonical prefix
within a specific AddressSpace.

Canonical identity shall use deterministic UUIDv5.

Identity inputs are:

- Stable AddressSpace UUID.
- Normalized CIDR, including address family and prefix length.
- NetworkPrefix model discriminator.

Conceptually:

    UUIDv5(
        NETWORK_PREFIX_NAMESPACE,
        "network-prefix:"
        + address_space_id
        + ":"
        + normalized_cidr
    )

The implementation must define a canonical serialization
format and apply it consistently.

Examples:

    global + 192.0.2.0/24
    LAB-A  + 192.0.2.0/24
    LAB-B  + 192.0.2.0/24

These represent three distinct canonical identities.

Within one AddressSpace:

    192.0.2.1/24
    192.0.2.0/24

normalize to the same NetworkPrefix identity when the first
value is interpreted as an interface address with prefix length.

The AddressSpace UUID and normalized CIDR together define
canonical uniqueness.

No legacy CIDR-only identity exception shall be retained.

This supersedes the previous CIDR-only NetworkPrefix identity
formula while preserving ADR-0006's deterministic identity
and state principles.

### 5. PrefixDiscoveryCandidate

PrefixDiscoveryCandidate represents a provisional prefix
identity undergoing discovery and reconciliation.

Candidate identity shall use an independent UUIDv4.

It shall not be calculated from:

- CIDR.
- AddressSpace.
- Source identity.
- Site.
- ASN.

A candidate may hold:

- Observed or normalized prefix information.
- Proposed AddressSpace reference.
- Discovery lifecycle status.
- First-seen and last-seen information.
- Correlation references.
- Resolution reference to a canonical NetworkPrefix.

These fields shall be finalized during implementation.

Candidate identity remains stable throughout its lifecycle.

A candidate may exist without a resolved AddressSpace.

A candidate may resolve to an existing NetworkPrefix or
participate in creating a new canonical NetworkPrefix.

The candidate itself is never silently replaced by the
canonical object.

### 6. Candidate Correlation

Prefix Discovery shall follow the same non-destructive
correlation principles as Device Discovery.

Candidate relationships support:

- possible
- confirmed
- rejected

Identical normalized CIDRs may provide evidence of a match.

However, CIDR equality without established AddressSpace
context shall not automatically prove canonical equivalence.

Different AddressSpaces may contain identical prefixes.

Weak evidence may produce a possible relationship.

Strong, unambiguous evidence or an authorized decision may
confirm a relationship.

Rejected relationships remain recorded.

Candidate relationship decisions must be traceable to
supporting evidence and actor information.

Candidate correlation must not automatically consolidate
candidate records.

Multiple candidates may resolve to the same canonical
NetworkPrefix without losing their original identities.

### 7. Candidate Lifecycle

Prefix discovery shall support a controlled candidate lifecycle.

The detailed lifecycle state model shall reuse established
Device Discovery patterns where applicable.

It must distinguish:

- Unresolved discovery candidates.
- Candidates awaiting validation or review.
- Candidates resolved to canonical prefixes.
- Rejected discoveries.
- Retired discovery records.

Candidate lifecycle, candidate relationship status, and
canonical prefix validation are separate concepts.

A rejected correlation does not necessarily mean that either
candidate is an invalid network.

Likewise, a resolved candidate does not imply that the
resulting prefix is operationally validated.

### 8. Reconciliation and Promotion

Prefix reconciliation shall evaluate whether a candidate:

1. Matches an existing canonical NetworkPrefix.
2. Matches an existing discovery candidate.
3. May be correlated with another candidate.
4. Qualifies for creation of a new canonical NetworkPrefix.
5. Requires further investigation or authorization.

Canonical creation requires:

- Valid normalized CIDR.
- Resolved AddressSpace.
- Canonical identity and collision checks.
- Sufficient evidence under applicable policy.
- Authorization where required.
- Preserved provenance and audit history.

Automatic promotion is permitted only when explicitly
authorized by reconciliation policy.

Manual promotion requires an authorized actor.

Source authority and promotion authority are distinct.

An external source cannot authorize canonical promotion
merely by asserting that its record is approved.

Reconciliation shall support idempotent repeated processing.

Existing canonical identity shall be reused rather than
duplicated.

### 9. Canonical Identity Versus Validation

Creation of a canonical NetworkPrefix establishes an accepted
logical identity.

It does not automatically establish:

- Operational reachability.
- Active utilization.
- Validated allocation.
- Confirmed site ownership.
- Confirmed ASN ownership.
- Approved routing or security classification.

Prefix lifecycle, operational state, validation state,
and administrative disposition shall be modeled separately.

Validation may change without changing canonical identity.

Existing evidence and authorized decisions must be retained.

### 10. Preserve Two-Layer Prefix Relationships

The architecture defined in ADR-0002 remains in force.

#### Layer 1 — Source to Canonical

Individual source observations shall connect to canonical
NetworkPrefix objects through explicit relationships.

Examples include:

    AsPrefix -> NetworkPrefix
    StaticRoute -> NetworkPrefix
    InterfaceAddress -> NetworkPrefix
    DHCPScopeObservation -> NetworkPrefix

Discovery candidates may hold provisional relationships
before canonical resolution.

Once resolved, the original source observations and their
canonical relationships remain traceable.

Evidence is used for provenance, not as a substitute
relationship registry.

#### Layer 2 — Canonical to Site

NetworkPrefix shall connect to Site or NetworkScope through
separately governed associations.

Site associations remain independent of canonical identity.

Existing association statuses remain:

- candidate
- inferred
- validated

ADR-0004 continues to govern projection and inference.

Candidate associations do not enter accepted scope projections.

Inferred associations may enter working projections but do not
become automatic inference seeds.

Validated associations may support further inference.

New inference shall not recursively validate itself.

### 11. NetworkScope and ASN

AddressSpace and NetworkScope remain distinct concepts.

AddressSpace defines address identity boundaries.

NetworkScope represents logical site/network groupings and
their associated prefixes, devices, and ASNs.

Existing NetworkScope ASN associations shall be preserved.

BGP AsPrefix identity remains source-aware under its
existing domain policy.

Observed BGP origin ASN does not automatically imply
administrative ownership of a canonical prefix.

Prefix-to-ASN and prefix-to-site findings remain governed
by existing analysis policies.

Existing findings include:

- prefix_multiple_asns
- asn_multiple_sites
- site_multiple_asns
- prefix_multiple_sites

These findings shall be evaluated with appropriate
AddressSpace context so that valid overlapping networks
are not automatically treated as identity conflicts.

### 12. Prefix Hierarchy

Prefixes may form hierarchical relationships within an
AddressSpace.

CIDR containment alone does not establish an authorized
administrative allocation relationship.

Administrative parent-child allocation relationships shall
be represented explicitly where required.

A parent allocation must not be invented merely to fill
a mathematical prefix hierarchy.

Independent AddressSpaces may contain identical or
overlapping prefixes without conflicting canonical identity.

Cross-AddressSpace relationships, where useful, must be
explicit rather than inferred from CIDR equality.

### 13. Evidence and Audit

Discovery and reconciliation shall preserve:

- Original observations.
- Original candidate identities.
- Candidate relationship history.
- Canonical resolution decisions.
- Supporting evidence references.
- Actor identity and authorization context.
- Decision timestamps and reasons.
- Reconciliation and validation outcomes.

Evidence and Findings remain owned by netvoyager-intelligence.

Historical records must not be destructively rewritten
merely because a newer discovery produces different information.

Related changes requiring atomic application shall use a
shared transaction and Unit of Work.

### 14. Persistence Architecture

The IPAM database implementation is greenfield.

No previously generated transient NetworkPrefix UUIDs
require persistent identity migration.

The initial persistent NetworkPrefix schema shall directly
implement AddressSpace-aware UUIDv5 identity.

No legacy identity mappings, historical UUID migration,
or old CIDR-only compatibility layer are required.

Database schema evolution shall continue through explicit
Alembic revisions.

The backend must not automatically execute schema migrations
on startup.

The database layer shall enforce the applicable uniqueness
and referential-integrity constraints.

Repositories shall participate in a caller-owned transaction
and shall not commit independently.

### 15. Package Responsibilities

#### netvoyager-network

Owns framework-independent domain definitions for:

- AddressSpace.
- NetworkPrefix.
- PrefixDiscoveryCandidate.
- Candidate relationships.
- Domain discovery decisions.

#### netvoyager-analysis

Owns:

- PrefixObservation.
- SourceDataset integration.
- Prefix normalization.
- Candidate correlation and reconciliation.
- Promotion policies.
- AddressSpace resolution policies.
- Repository and Unit of Work protocols.
- Prefix, site, ASN, and allocation analysis.

#### netvoyager-intelligence

Owns:

- Evidence.
- Findings.
- Provenance and intelligence concepts.

#### netvoyager-database

Owns:

- SQLAlchemy persistence entities and mappings.
- Repository implementations.
- Database sessions and Unit of Work.
- Schema definition and Alembic revisions.
- Persistent relationship and audit storage.

#### Source and Integration Packages

Own source-specific acquisition and transformation.

They shall translate collected data into standardized
observations without bypassing discovery or reconciliation.

### 16. Implementation Sequence

Implementation shall proceed incrementally:

1. Define AddressSpace domain identity and default global space.
2. Update NetworkPrefix with AddressSpace-aware UUIDv5 identity.
3. Add focused domain identity and uniqueness tests.
4. Implement PrefixObservation and SourceDataset integration.
5. Implement PrefixDiscoveryCandidate and candidate relationships.
6. Implement prefix correlation and reconciliation policies.
7. Implement authorized canonical promotion and resolution.
8. Introduce required SQL entities, repositories, and migrations
   incrementally as each workflow requires persistence.
9. Restore source-to-canonical prefix relationships.
10. Restore prefix-to-site and NetworkScope relationships.
11. Integrate ASN analysis, findings, and provenance.
12. Run focused integration and end-to-end regression tests.

Before modifying each component, inspect the relevant current
implementation, protocols, consumers, tests, and package exports.

Production Analysis shall remain independent of concrete
Database implementations.

### 17. Testing Requirements

Tests shall verify:

- Deterministic global AddressSpace identity.
- Stable AddressSpace identity.
- Distinct canonical UUIDs across AddressSpaces.
- Identical canonical UUIDs for normalized equivalent
  prefixes in the same AddressSpace.
- IPv4 and IPv6 support.
- Independent candidate UUIDs.
- Preservation of repeated source observations.
- Possible, confirmed, and rejected correlations.
- Resolution of multiple candidates to one canonical prefix.
- Matching and reuse of existing canonical prefixes.
- Rejection of unauthorized promotion.
- Idempotent reconciliation.
- Transaction rollback and referential integrity.
- Preservation of evidence and audit history.
- AddressSpace-aware site and ASN conflict analysis.

Committed tests shall use synthetic infrastructure data only.

## Consequences

### Benefits

- Prefix discovery follows established NetVoyager principles.
- Canonical prefixes have deterministic, address-space-aware identity.
- Overlapping networks are supported.
- Source observations remain independent.
- Discovery candidates are auditable and non-destructive.
- Canonical promotion is governed.
- Site and ASN ownership remain independently validated.
- The domain model remains independent of external platforms.
- Greenfield persistence avoids legacy identity compatibility.

### Costs

- Additional discovery and relationship models are required.
- Reconciliation becomes a distinct workflow.
- AddressSpace resolution requires explicit policy.
- Canonical promotion requires dedicated authorization tests.
- Persistent relationships and audit records increase schema complexity.

## Relationship to Existing ADRs

- ADR-0002: Preserves the two-layer prefix relationship design.
- ADR-0003: Preserves individual source observations.
- ADR-0004: Preserves prefix-site status and scope projection.
- ADR-0005: Preserves prefix selection and inference policies.
- ADR-0006: Preserves deterministic UUIDv5 principles while
  superseding CIDR-only NetworkPrefix identity.
- ADR-0009: Reuses established discovery and reconciliation principles.
- ADR-0013: Reuses manual approval and authorization principles.
- ADR-0016: Preserves established persistence ownership boundaries.
- ADR-0017: Preserves platform-independent domain boundaries.

## Implementation Status

Architecture accepted.

The initial persistent IPAM model shall be implemented directly
using the rules established in this ADR.

No historical canonical prefix migration is required.

Implementation shall begin with AddressSpace and NetworkPrefix
domain identity, followed by Prefix Discovery.
