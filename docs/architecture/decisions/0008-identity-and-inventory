
# NetVoyager — Identity and Inventory Decisions

**Date:** 2026-10-13
**Status:** Accepted

## Model Identity

| Model | UUIDv5 Identity | State UUID |
|---|---|---|
| NetworkPrefix | CIDR | Not required |
| AsPrefix | Source UUID + CIDR + ASN | Deferred |
| AutonomousSystem | ASN | Not required |
| NetworkDevice | Imported unique name | UUIDv5 |

## Physical Device Representation

- One NetworkDevice represents one physical inventory device.
- Multiple physical devices may share a management IP.
- Serial number is a state field, not an identity field.
- Physical replacement changes state, not identity, when the imported name remains unchanged.
- Stack and virtual-chassis modeling are deferred.

## Excel Inventory

- Duplicate name policy: prefix (default).
- Duplicate serial policy: warn (default).
- Duplicate names become DUP-{row_number}-{original_name}.
- Every occurrence of a duplicate name is prefixed.
- Unique names remain unchanged.
- Duplicate serial numbers never cause records to be merged.
- Original inventory values are preserved in raw_line.

## Future Canonical Naming

- Continue using legacy inventory names during transition.
- Prepare legacy-to-canonical name mappings.
- Establish a new UUIDv5 identity baseline at go-live.
- Rebuild dependent references consistently.
- Retaining legacy UUIDs after migration is not required.

## Evidence and Relationships

- EvidenceStore stores provenance only.
- Repeated observations must retain distinct evidence records.
- Source-to-canonical and canonical-to-site relationships remain separate.
- Only validated site-prefix associations can seed further inference.
