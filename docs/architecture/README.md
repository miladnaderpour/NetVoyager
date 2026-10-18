# NetVoyager architecture documentation

These documents capture architectural decisions accepted in discussion through **2026-10-18**. The ADR formatting follows the supplied example (`Status`, `Context`, `Decision`, `Consequences`). The accompanying overview follows the structure of the supplied architecture overview, adapted for NetVoyager.

## Read in this order

1. [`overview.md`](overview.md) — concise big picture.
2. [`decisions/`](decisions/) — accepted architecture decision records (ADRs), including later clarifications.
3. [`current-workflow.md`](current-workflow.md) — what the supplied integration script actually does today.
4. [`implementation-plan.md`](implementation-plan.md) — suggested sequencing and **still-open field-level specifications**.
5. [`handover-2026-10-18.md`](handover-2026-10-18.md) — package migration checkpoint, validation results, and next steps.

## Decision index

| ADR | Topic |
|---|---|
| [0001](decisions/0001-keep-network-domain-models-simple.md) | Keep domain models simple |
| [0002](decisions/0002-two-layer-prefix-relationships.md) | Two-layer relationship architecture |
| [0003](decisions/0003-preserve-individual-source-observations.md) | Preserve every individual source observation |
| [0004](decisions/0004-prefix-site-status-and-scope-projection.md) | Site association statuses and scope projection |
| [0005](decisions/0005-panorama-prefix-selection-and-inference.md) | Panorama selection and inference |
| [0006](decisions/0006-uuid5-identity-and-state.md) | UUIDv5 identity/state and scope UUIDs |
| [0007](decisions/0007-repeatable-discovery-and-change-detection.md) | Repeatability and change detection |
| [0008](decisions/0008-identity-and-inventory.md) | Identity and inventory |
| [0009](decisions/0009-evidence-driven-device-discovery-and-reconciliation.md) | Evidence-driven device discovery and reconciliation |
| [0010](decisions/0010-inventory-evidence-and-repeated-imports.md) | Inventory evidence and repeated imports |
| [0011](decisions/0011-storage-architecture-and-model-separation.md) | Storage architecture and model separation, with Intelligence extraction addendum |
| [0012](decisions/0012-device-renaming-and-hardware-replacement.md) | Canonical device renaming and hardware replacement |
| [0013](decisions/0013-manual-and-batch-device-identity-approval.md) | Manual and batch device identity approval |
| [0014](decisions/0014-intelligence-package-boundary.md) | Intelligence package ownership; persistence strategy remains open |
| [0015](decisions/0015-retire-storage-package.md) | Retire Storage; Analysis owns Protocols and Database owns persistence exceptions |

The supplied Intelligence decision was numbered ADR-0012. It is recorded here
as ADR-0014 because ADR-0012 already covers device renaming and hardware
replacement. Existing ADR numbers and references are preserved.

**Status convention:** `Accepted` means architecture agreed, not necessarily implemented. Avoid treating proposals in `implementation-plan.md` as accepted decisions.
