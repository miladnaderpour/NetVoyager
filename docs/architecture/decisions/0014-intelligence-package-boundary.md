# ADR-0014 — Dedicated Intelligence Package and Ownership Boundaries

## Status
Accepted — package extraction; persistence strategy remains open

Subsequent decision: [ADR-0015](0015-retire-storage-package.md) resolves the
Storage retention question by retiring the package. Its Protocols belong to
Analysis and its exceptions to Database. Intelligence persistence and concrete
Database imports in Analysis remain separate, unresolved choices. References
below to Storage being undecided describe this ADR's original decision scope.

## Date
2026-10-18

## Context
NetVoyager currently maintains evidence and finding models and in-memory stores under `netvoyager-analysis`. The project is adding SQLAlchemy-based persistence in `netvoyager-database`, while retaining independent network-domain models in `netvoyager-network`.

During the database migration, moving evidence models into `netvoyager-network` was proposed to resolve dependency direction. That would incorrectly assign evidence ownership to the network domain. Keeping evidence solely in `netvoyager-analysis` also makes it awkward for the persistence layer to consume evidence models without coupling database infrastructure to analysis algorithms. Meanwhile, duplicating every persistent record as both a dataclass and an ORM entity may add boilerplate and mapping complexity.

Evidence and findings are first-class concepts with their own lifecycle, references, and consumers. Their package ownership should be explicit before changing persistence representations.

## Decision

1. Introduce **`netvoyager-intelligence`** as a separate distributable Python package (`netvoyager_intelligence`).
2. The intelligence package owns evidence and findings **models and associated store behavior**. Evidence and findings do not belong to `netvoyager-network`.
3. `netvoyager-analysis` owns analysis algorithms and orchestration: matching, inference, validation, reconciliation, policy, and production/interpretation of evidence and findings. It consumes intelligence concepts without defining duplicate versions of them.
4. `netvoyager-database` owns SQLAlchemy integration, repository implementations, database connections, and transaction mechanics. Any ORM-native intelligence-model decision must be made explicitly after inspecting actual use sites and import dependencies.
5. First migrate **without changing model behavior**. Preserve identity, timestamps, link semantics, ordering, APIs, and existing analysis behavior. Compatibility re-exports in the old analysis paths are temporary migration aids, not permanent ownership.
6. Preserve the distinction between **evidence as provenance** and **operational device/prefix relationships**. Evidence links must not silently become a device identity matcher.
7. Use focused regression tests and run the established analysis and database suites before removing compatibility imports.

## Initial package scope

```text
packages/netvoyager-intelligence/
  pyproject.toml
  src/netvoyager_intelligence/
    __init__.py
    evidence/
      __init__.py
      models.py
      store.py
    findings/
      __init__.py
      models.py
      store.py
```

The initial scope intentionally does **not** include all candidate decisions, assertions, or policy models. These may be evaluated later based on their true domain ownership and imports; no indiscriminate relocation is authorized by this ADR.

## Dependencies and intended boundaries

- `netvoyager-analysis` may import `netvoyager-intelligence`.
- `netvoyager-database` may consume intelligence models after choosing and validating a suitable persistence integration.
- `netvoyager-network` stays focused on the network domain and is not made the owner of evidence/findings.
- Avoid circular dependencies; inspect installed package metadata, code imports, and project configuration before locking the complete graph.
- The final role or removal of `netvoyager-storage` remains **undecided**. A discussion favoring removal is not an applied migration.

## Explicitly deferred choices

- Whether evidence and findings become ORM-native or remain plain dataclasses mapped to ORM entities.
- Whether `netvoyager-analysis` imports `netvoyager-database` directly for workflows, and where optional repository Protocols should live.
- How to persist evidence references in discovery relationships (currently JSON UUID lists in the implemented SQLAlchemy entity) and how to enforce referential integrity.
- Persistence for discovery decisions, attribute assertions, finding lifecycle, and evidence history.
- Whether `netvoyager-storage` is retired, retained for narrower contracts, or reorganized.

These decisions require separate examination of real source code, dependency cycles, operational requirements, and tests. Do not infer them from package extraction alone.

## Consequences

**Benefits**
- Evidence/findings have a clear domain owner without contaminating `netvoyager-network`.
- Analysis algorithms need not own storage records.
- Database integration can be developed incrementally.
- Existing code can remain functional through temporary compatibility imports.

**Costs and risks**
- A new distributable and install dependency must be maintained.
- Imports and project package metadata must be updated.
- Compatibility modules can obscure ownership if left indefinitely.
- ORM/model design and `netvoyager-storage` decisions are still outstanding.

## Relationship to previous ADRs

- **ADR-0011** remains a record of the accepted earlier storage architecture, but its package-ownership examples and assumptions need reconciliation with this newer decision. This ADR supersedes ADR-0011 **only where there is a conflict about evidence/finding ownership**; it does not by itself reverse all storage independence or storage-package decisions.
- Earlier evidence and discovery decisions remain in force, especially non-destructive evidence provenance and separate operational matching.

## Implementation checkpoint

An extraction patch named `netvoyager_intelligence_extraction_patch.zip` was prepared from an available NetVoyager repository snapshot. It adds the package, copies evidence and findings model/store implementations, introduces compatibility re-exports in analysis, adds an analysis package dependency, and includes two migration-focused tests. The archive is a proposed patch, **not evidence it has been applied to the user's local checkout**. The complete latest suite has not been rerun here. Previously reported database baseline: **46 passing tests**.
