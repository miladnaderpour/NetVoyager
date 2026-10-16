# ADR-0010 — Preserve Excel Import Evidence and Separate Observations from State Changes

## Status

Accepted (design); implementation details and integration verification pending.

## Date

2026-10-16

## Context

Excel remains the initial inventory baseline through `netvoyager-import`, not `netvoyager-discovery`. The importer creates source observations, including duplicated identifiers and incomplete rows. `process_device_observations()` creates canonical physical `NetworkDevice` objects and links evidence where identity is available. Repeated imports may observe an unchanged device multiple times; a new provenance record is not necessarily a changed device.

## Decision

- Keep Excel ingestion in `netvoyager-import`, and canonical processing and evidence linking in `netvoyager-analysis`. Do not generate discovery candidates for every valid baseline inventory row.
- Preserve every nonempty Excel row as a distinct observation and generate an `EvidenceRecord` for it, including when its name is missing.
- Create exactly one `NetworkDevice` for each observation whose imported/resolved name is usable. Duplicate names are resolved upstream as `DUP-{row_number}-{original_name}` for every member of a duplicate-name group.
- If the name is missing, warn, preserve evidence, and do not create a nameless canonical device.
- Duplicate serial numbers or shared management IPs never merge distinct inventory physical devices.
- Link each resolvable row's evidence ID to its canonical device UUID via `EvidenceStore.link()`; preserve original row values and row number. Unresolved records remain queryable as evidence even without a canonical device link.
- Treat separate import runs as separate observations: produce a fresh provenance record for each imported row occurrence, even when source values are unchanged.
- Compare canonical identity and designated technical `state_id` to identify meaningful changes. Additional evidence alone does not imply a state change. Attribute enrichment is distinct from hardware replacement.
- Record sufficient source context to identify input file, worksheet, row and import/collection session when the run-context schema is implemented. Avoid assuming a filepath string alone is a globally unique source identity.
- Preserve import validation issues, such as duplicate serial warnings, in a way that is associated with the relevant observation; a validation issue is not itself strong proof of physical identity. Exact issue linkage schema is deferred.
- Later Excel imports against a persistent existing baseline should reconcile with canonical devices rather than blindly append duplicate canonical entries; the reconciliation contract remains to be designed.

## Consequences

- Each canonical device can show provenance from its initial Excel row and later independent discovery sources.
- Historical observations remain available without generating spurious technical-state changes.
- The one-row-per-physical-device baseline model and UUIDv5 naming contract remain intact.
- Import-session identity, evidence indexing/persistence, issue-to-evidence relationships, baseline refresh behavior and complete regression remain implementation work.

## Related decisions

ADR-0003, ADR-0006, ADR-0007, ADR-0008, ADR-0009.
