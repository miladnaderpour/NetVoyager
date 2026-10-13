# 0003 - Preserve individual source observation relationships

## Status

Accepted

## Context

Several AsPrefix records may share a CIDR and ASN. Duplicate-valued observations may still carry distinct source and run context.

## Decision

- Retain every individual source-to-canonical observation relationship.
- Do not collapse five distinct `AsPrefix` observations into one relationship merely because their CIDR and ASN agree.
- Aggregate ASN values only where a consumer needs distinct ASN assignments.
- Plan sources: BGP `AsPrefix`, Palo Alto `StaticRoute`, Palo Alto `InterfaceAddress`, and future DHCP scope observations.

## Consequences

- Subsequent analysis can navigate exact observations and their attributes without querying `EvidenceStore`.
- Observation membership and identity must be handled explicitly across collection runs.
