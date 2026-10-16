
# ADR-0009: Evidence-Driven Device Discovery and Reconciliation

- **Status:** Accepted
- **Date:** 2026-10-13
- **Project:** NetVoyager
- **Scope:** Device discovery, candidate correlation, reconciliation, merging, promotion, and evidence provenance
- **Implementation Status:** Pending

## 1. Context

NetVoyager is evolving from an inventory-based network analysis platform into a multi-source, evidence-driven discovery and reconciliation system.

The platform must collect information from various sources, including:

- Excel inventory
- Direct network device connections (CLI and APIs)
- Network controllers and management platforms
- Palo Alto Panorama and Strata
- Cisco network devices and controllers
- Fortinet devices and management platforms
- Meraki Dashboard
- LLDP/CDP neighbor discovery
- Future network discovery integrations

These sources provide different levels of information and reliability.

A device may be discovered multiple times through independent sources without initially having sufficient information to establish its physical identity.

For example:

1. LLDP reports a neighboring hostname and chassis ID.
2. A controller reports a device with the same hostname and management IP.
3. Direct device collection later provides a physical serial number.
4. NetVoyager correlates the observations and eventually establishes a canonical physical-device identity.

However, multiple physical devices may legitimately share:

- Hostname
- Management IP
- Stack management interfaces
- Certain reported device identifiers

Therefore, observations must not be merged automatically based on weak or ambiguous identity attributes.

The architecture must support progressive discovery, evidence accumulation, candidate reconciliation, and eventual canonical device creation.

## 2. Decision

NetVoyager will introduce an evidence-driven Device Discovery Registry.

The registry will support:

1. Provisional device candidates.
2. Evidence-based candidate correlation.
3. Non-destructive candidate merging.
4. Canonical device reconciliation and promotion.
5. Preservation of complete discovery history.
6. Reversible reconciliation decisions.
7. Efficient evidence retrieval by candidate or canonical device identity.

Candidate correlation, merging, and promotion are separate operations with distinct responsibilities.

## 3. Device Discovery Candidate

A `DeviceDiscoveryCandidate` represents a hypothesized physical network device whose canonical identity has not yet been established.

A candidate is not a `NetworkDevice`.

### 3.1 Identity

Each candidate has an independent `candidate_id`.

Candidate identity must not depend directly on:

- Hostname
- Management IP
- Serial number
- Inventory name

These attributes may be missing, duplicated, or changed as new evidence becomes available.

A generated UUID independent of those attributes is recommended.

The final UUID generation strategy will be defined during model implementation.

### 3.2 Lifecycle

The proposed candidate lifecycle includes:

| Status | Description |
|---|---|
| `candidate` | Initial discovery with insufficient identity evidence |
| `corroborated` | Additional observations support the candidate |
| `resolved` | Candidate is associated with a canonical NetworkDevice |
| `rejected` | Candidate is determined to be invalid or a false discovery |
| `retired` | Candidate is no longer active or relevant |

Candidate lifecycle status must remain separate from candidate relationship status.

### 3.3 Important Rule

**Corroborated does not mean promotable.**

Multiple weak observations may support the existence of a device without establishing its unique physical identity.

Promotion requires sufficiently strong, unambiguous evidence.

## 4. Candidate Correlation

Multiple candidates may represent the same physical device.

NetVoyager must support relationships between candidates without immediately merging them.

### 4.1 Relationship Status

The candidate relationship model will support:

| Status | Meaning |
|---|---|
| `possible` | Evidence suggests candidates may represent the same device |
| `confirmed` | Sufficient evidence establishes a common physical identity |
| `rejected` | The proposed relationship must not be used for reconciliation |

These statuses describe relationships, not candidate lifecycle states.

### 4.2 Correlation Rules

- Weak evidence may establish a possible relationship.
- Possible relationships do not automatically merge candidates.
- Shared hostname alone is insufficient to confirm identity.
- Shared management IP alone is insufficient to confirm identity.
- Multiple physical stack members may share hostname and management IP.
- Strong identity evidence is required before confirming that two candidates represent the same physical device.
- Contradictory evidence must prevent unsafe confirmation.

Candidate relationships must be maintained by the discovery registry rather than reconstructed from EvidenceStore.

## 5. Candidate Merging

Candidates may be consolidated when sufficient evidence establishes that they represent the same physical device.

### 5.1 Merge Principles

- Merging is non-destructive.
- Original candidate IDs must be preserved.
- Original observations and evidence must remain accessible.
- Merge decisions must be traceable to their supporting evidence.
- Merged candidates must retain their individual historical identities.
- Merging must be reversible if stronger evidence later contradicts the decision.

A confirmed candidate relationship does not require immediate promotion to `NetworkDevice`.

### 5.2 Incorrect Merge Recovery

If later discovery proves that previously merged candidates represent different physical devices:

1. Preserve the original evidence.
2. Record the contradictory evidence.
3. Reverse or invalidate the confirmed relationship.
4. Restore the independent candidate relationships.
5. Reevaluate affected canonical device associations.

The exact rollback and reconciliation interfaces will be designed during implementation.

## 6. Canonical Device Promotion

Promotion establishes or associates a candidate with a canonical `NetworkDevice`.

### 6.1 Promotion Eligibility

Promotion requires strong, unambiguous physical-device identity evidence.

Examples of strong evidence include:

- Direct device inventory containing an identifiable physical chassis serial.
- Direct device collection reporting reliable physical hardware information.
- Controller or management API providing a reliably identified physical-device serial.

Evidence strength must be evaluated in relation to the entity being reported.

For example, a Cisco stack-level `show version` output may describe the logical stack, whereas `show inventory` may identify individual physical members.

### 6.2 Promotion Rules

- Promotion must first attempt reconciliation against existing canonical devices.
- A new `NetworkDevice` may be created only when a sufficiently reliable, unique identity is established.
- Existing device identities must not be replaced accidentally.
- Several candidates may resolve to the same canonical device.
- A candidate may be promoted directly without first merging with other candidates.
- Evidence from unresolved or merged candidates must remain accessible after promotion.
- Conflicting evidence prevents automatic promotion until the ambiguity is resolved.

The deterministic naming policy for newly discovered canonical devices remains to be designed.

The existing UUIDv5 identity contract for `NetworkDevice` must be preserved.

## 7. Evidence Architecture

NetVoyager's existing `EvidenceStore` remains the central provenance repository.

### 7.1 Evidence Responsibilities

EvidenceStore must preserve:

- Original observations
- Reporting source
- Collection context
- Collected attributes
- Supporting identity evidence
- Candidate associations
- Canonical device associations
- Reconciliation decision provenance

EvidenceStore must not become the operational device relationship index.

### 7.2 Device Evidence Retrieval

Users must be able to retrieve all evidence associated with a canonical device by its `device_id`.

The evidence history must include:

- Evidence collected directly from the device
- Evidence reported by other devices
- Controller and dashboard observations
- Inventory records
- LLDP/CDP observations
- Historical discovery candidates subsequently resolved to the device
- Enrichment and reconciliation decision records

Evidence should remain accessible regardless of whether the original source was direct or indirect.

### 7.3 Candidate Evidence Retrieval

Users must be able to retrieve all evidence associated with a discovery candidate by its `candidate_id`.

When a candidate is resolved:

- Preserve existing candidate-to-evidence relationships.
- Preserve the original evidence record IDs.
- Make the relevant evidence accessible through the canonical device.
- Do not duplicate evidence records unnecessarily.
- Maintain a traceable candidate-to-device resolution relationship.

### 7.4 Evidence Indexing

Efficient reverse lookup by object type and object UUID is required.

The implementation may extend EvidenceStore indexing to support scalable object-level evidence retrieval.

The existing `for_object()` interface should be preserved unless a documented architectural reason requires modification.

## 8. Package Responsibilities

### `netvoyager-discovery`

Responsible for discovery orchestration:

- Connecting to collection targets
- Coordinating collection sessions
- Executing vendor-specific collectors
- Managing collection scheduling and retries
- Delivering source observations to downstream processing

This package must not own canonical device reconciliation or candidate relationship decisions.

### Vendor-Specific Packages

Examples include `netvoyager-paloalto` and future Cisco/Fortinet adapters.

Responsible for:

- Vendor-specific connections and APIs
- CLI command execution
- Parsing vendor-specific data
- Producing structured source observations

### `netvoyager-import`

Responsible for file-based source imports, including Excel inventory validation and normalization.

### `netvoyager-network`

Responsible for vendor-neutral canonical domain models.

`NetworkDevice` continues to represent one physical inventory device.

### `netvoyager-analysis`

Responsible for:

- Device matching
- Device enrichment
- DeviceDiscoveryCandidate management
- DeviceDiscoveryStore
- Candidate relationships
- Evidence evaluation
- Candidate reconciliation and promotion
- Identity conflicts and related findings

### `EvidenceStore`

Responsible for provenance and evidence-object relationships.

It must not replace operational discovery or canonical-device relationship stores.

## 9. Matching and Enrichment Integration

Existing matching and enrichment responsibilities remain separate.

### Matching

`match_devices()` identifies existing canonical devices using the established priority:

1. Serial number
2. Hostname
3. Management IP

Shared hostname or management IP must not cause arbitrary physical-device selection.

Ambiguous matches remain unresolved.

### Enrichment

`enrich_device()` updates attributes of an already resolved device.

The agreed generic enrichment policy remains:

- `overwrite=False`: Populate missing values and report conflicts without replacing existing values.
- `overwrite=True`: Permit replacement of conflicting attributes after sufficiently reliable matching.

The initial enrichment implementation supports hostname updates.

Future extensions may support other technical attributes.

Enrichment must not change `NetworkDevice.name` or `device_id`.

The overwrite policy must never bypass identity-matching or candidate-promotion requirements.

## 10. Evidence Strength

Evidence strength will initially be evaluated using explicit and explainable rules.

A generic numeric confidence score will not be introduced at this stage.

Evidence assessment must consider:

- Source reliability
- Direct versus indirect observation
- Physical versus logical device context
- Available identity attributes
- Contradictory observations
- Whether the evidence uniquely identifies one physical device

Repeated weak evidence must not automatically become strong physical identity evidence solely because of observation count.

## 11. Discovery Registry Responsibilities

`DeviceDiscoveryStore` will own operational candidate management.

Its responsibilities include:

- Registering new candidates
- Indexing candidates
- Maintaining candidate lifecycle status
- Maintaining candidate relationships
- Tracking confirmed and possible correlations
- Supporting evidence-backed merge decisions
- Supporting reversible reconciliation
- Tracking candidate-to-canonical-device resolution

It must not duplicate the complete source-observation history stored by EvidenceStore.

## 12. Architectural Guarantees

The following guarantees are mandatory:

1. A canonical NetworkDevice represents one physical device.
2. Weak evidence cannot automatically merge physical-device identities.
3. Multiple candidates may eventually resolve to one NetworkDevice.
4. Original candidate identities and evidence are never discarded during reconciliation.
5. Candidate merging and canonical promotion are independent operations.
6. Conflicting evidence must be preserved and investigated rather than silently overwritten.
7. Evidence relationships remain accessible after promotion.
8. Candidate relationship history must support reversal.
9. EvidenceStore provides provenance, not operational relationship lookup.
10. Canonical NetworkDevice identity remains deterministic.
11. Discovery collection and reconciliation responsibilities remain separated.
12. Candidate lifecycle status does not itself establish promotion eligibility.

## 13. Deferred Design Decisions

The following require separate design reviews:

- Exact `DeviceDiscoveryCandidate` model fields and types
- Candidate UUID generation implementation
- `DeviceDiscoveryCandidateRelationship` identity and fields
- Relationship transition rules
- Candidate merging and rollback interfaces
- `DeviceDiscoveryStore` indexes and lookup methods
- Strong-evidence promotion eligibility rules
- Stable naming convention for newly discovered devices
- Collection-session identity and provenance model
- EvidenceStore reverse-index implementation
- Persistent storage and discovery history
- Candidate retirement and cleanup policy
- Full device discovery pipeline integration

These items are intentionally not decided by this ADR.

## 14. Implementation Sequence

1. Design `DeviceDiscoveryCandidate`.
2. Design `DeviceDiscoveryCandidateRelationship`.
3. Define relationship lifecycle and reversible transitions.
4. Design `DeviceDiscoveryStore` and its indexes.
5. Review EvidenceStore reverse lookup and candidate-resolution evidence access.
6. Define reconciliation and promotion policies.
7. Integrate matching and enrichment.
8. Integrate collection orchestration through `netvoyager-discovery`.
9. Validate multi-source and multi-candidate discovery scenarios.

All implementation must follow existing NetVoyager model conventions, docstring style, typing, logging, and package boundaries.

## 15. Consequences

### Benefits

- Supports progressive discovery from multiple independent sources.
- Avoids unsafe physical-device merges.
- Preserves complete evidence and reconciliation history.
- Allows automated creation of strongly identified devices.
- Supports manual investigation of ambiguous devices.
- Keeps discovery orchestration separate from analysis.
- Enables future evidence-driven inventory enrichment.
- Supports reconciliation recovery when earlier assumptions prove incorrect.

### Trade-offs

- Requires additional candidate and relationship models.
- Introduces reconciliation lifecycle complexity.
- Requires candidate indexing and evidence lookup optimization.
- Requires explicit handling of conflicting identity observations.
- Requires careful management of candidate-to-canonical-device transitions.

These trade-offs are accepted to support reliable, scalable network discovery.

## 16. Decision Summary

NetVoyager will maintain an evidence-driven Device Discovery Registry in which unresolved physical-device candidates can accumulate observations from multiple sources.

Candidates may be correlated using weak evidence but must not be merged without sufficient proof of common physical identity.

Merging and promotion are separate, non-destructive, evidence-backed operations.

Strong, unambiguous physical identity evidence may justify automatic creation of a canonical NetworkDevice.

All original candidate identities, supporting evidence, and reconciliation decisions must remain accessible and auditable.

**Status: ACCEPTED — Implementation pending.**
