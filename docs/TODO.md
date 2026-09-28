# NetVoyager TODO

## Planned: NetworkInventory

Introduce a shared container for devices, autonomous systems, and scopes.

Potential responsibilities:
- Indexed lookup by device ID, ASN, and scope ID.
- Duplicate identity detection.
- Scope hierarchy validation and cycle prevention.
- Cross-scope prefix assignment checks.
- Reverse lookup of scopes associated with an ASN.

Resolve before implementation:
- Stable device identity across import sources.
- Update and merge rules.
- How inventory-wide checks interact with mutable models.
- Treatment of identical prefixes in different routing contexts.

Deferred until the initial analysis workflow clarifies the required interface.

## Next: Analysis package

- Adapt network grouping, filtering, and matching to the new models.
- Create netvoyager_analysis for correlation, evidence, and conflicts.
- Define the mapping from device site references to scope IDs.
- Keep suggested relationships separate from accepted scope assignments.