# NetVoyager architecture documentation

These documents capture architectural decisions accepted in discussion through **2026-10-12**. The ADR formatting follows the supplied example (`Status`, `Context`, `Decision`, `Consequences`). The accompanying overview follows the structure of the supplied architecture overview, adapted for NetVoyager.

## Read in this order

1. [`overview.md`](overview.md) — concise big picture.
2. [`decisions/`](decisions/) — seven accepted architecture decision records (ADRs).
3. [`current-workflow.md`](current-workflow.md) — what the supplied integration script actually does today.
4. [`implementation-plan.md`](implementation-plan.md) — suggested sequencing and **still-open field-level specifications**.

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

**Status convention:** `Accepted` means architecture agreed, not necessarily implemented. Avoid treating proposals in `implementation-plan.md` as accepted decisions.
