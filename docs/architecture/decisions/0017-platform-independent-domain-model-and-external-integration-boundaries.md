# ADR-0014: Platform-Independent Domain Model and External Integration Boundaries

- **Status:** Accepted
- **Date:** 2026-10-21
- **Scope:** All NetVoyager domain models, discovery, reconciliation,
  integration, and persistence.

## Context

NetVoyager collects, normalizes, correlates, validates, and manages network
information from heterogeneous sources.

External systems may provide inventory, configuration, topology, addressing,
operational state, and administrative information.

These systems may use different object models, identifiers, relationships,
classifications, and validation processes.

NetVoyager must remain independently operational while supporting flexible
integration with external platforms.

## Decision

### 1. Independent Domain Model

NetVoyager shall maintain its own domain entities, identities, relationships,
policies, and lifecycle states.

External platform schemas shall not determine NetVoyager's internal architecture.

### 2. Separation of Acquisition and Domain Modeling

Data acquisition and integration mechanisms shall remain separate from domain
models.

External information shall enter through adapters and standardized source
observations.

### 3. Discovery and Reconciliation

Incoming information shall be processed according to NetVoyager's discovery,
identity, reconciliation, and authorization policies.

External identifiers or assertions shall not automatically establish canonical
identity or validated relationships.

### 4. Canonical Entities

Canonical entities shall use NetVoyager-defined identity rules.

External identifiers shall be maintained through explicit mappings for
traceability and synchronization.

### 5. Flexible Integration

Integrations may support:

- Inbound collection and synchronization.
- Outbound publication of authorized canonical information.
- Bidirectional synchronization with explicit ownership and conflict-resolution
  policies.

### 6. Field-Level Authority

Data authority shall be defined by source, field, collection method, and
applicable policy rather than by a universal source ranking.

An external system may be authoritative for selected attributes without
controlling the complete canonical object.

### 7. Evidence, Validation, and Audit

Source observations, provenance, validation state, and authorized decisions
shall remain independently traceable.

External synchronization shall not bypass NetVoyager's validation,
authorization, or audit requirements.

### 8. Persistence Independence

Domain models shall remain independent of particular database implementations
and external platform schemas.

Persistence and integration mappings shall be implemented through dedicated
infrastructure components and repository abstractions.

## Consequences

- NetVoyager can operate without external management platforms.
- External integrations can be added, replaced, or removed without
  redesigning core domain identities.
- Integration adapters may require explicit translation and reconciliation.
- Bidirectional synchronization requires durable external identity mappings
  and conflict handling.
- Canonical data remains governed by NetVoyager policies.

## Implementation Guidance

This ADR establishes architectural boundaries only.

It does not mandate specific integration technologies, synchronization
schedules, database structures, or external API contracts.

Detailed IPAM, device discovery, and other domain decisions remain governed
by their respective ADRs.