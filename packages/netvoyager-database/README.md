# NetVoyager unified database — model checkpoint

This experimental package uses SQLAlchemy ORM classes as domain models and supports in-memory and file-based SQLite.

## This checkpoint
- One `record_type` on primary domain entities (observation/candidate/canonical).
- `state_id` on entity records; promotion keeps `id` and creates a new `state_id` with audit references.
- `Device.device_type` physical/logical, optional `logical_key`; hostname and management IP are not unique.
- Optional `NetworkPrefix` VRF, VLAN, operational status, and description.
- Location hierarchy via `parent_location_id`.
- UUIDv4 primary identities; exact serial matching (no leading-zero recovery).

**This is an intermediate model checkpoint, not a migration-ready or production schema.** Existing Alembic revision 0001 is from the preceding prototype and intentionally has NOT been regenerated. Do not run it for this model revision. Next steps: canonical uniqueness and relationship constraints (including interface connectivity), then regenerate and test the initial Alembic migration.

## Focused tests
```sh
python -m pip install -e ".[test]"
python -m pytest -q
```

# NetVoyager Unified Database — database-first experiment

This is a **new-branch prototype**, not a drop-in replacement for the old `dev` code. It consolidates domain objects and SQLAlchemy entities into one ORM model each. No separate `netvoyager-network` or `netvoyager-intelligence` package is needed.

## Layout

- `src/netvoyager_database/models/`: one ORM model per file, `base.py`, `relationships/` and `history/`.
- `src/netvoyager_database/repositories/`: a thin repository per primary entity, with shared mechanics in `base.py`.
- `src/netvoyager_database/engine.py`, `session.py`, `unit_of_work.py`: connection and transaction handling.
- `src/netvoyager_database/migrations/`: the original initial Alembic revision, retained to match the ORM schema.
- `src/netvoyager_database/lifecycle.py`: demonstration lifecycle operations (authorization must be enforced by future Analysis).
- `tests/`, `examples/`: self-contained synthetic checks and lifecycle example.

Every primary entity uses `record_type` (`observation`, `candidate`, `canonical`). The original observation can remain a separate immutable row; candidate promotion updates the same entity ID and an append-only event records the transition.

## Run

```powershell
python -m pip install -e ".[test]"
python -m pytest -q
python -m netvoyager_database.migrations upgrade --url sqlite:///experiment.db
python examples/lifecycle_demo.py
```

No migrations run automatically on application startup. Test-only `Base.metadata.create_all` is intentionally restricted to disposable databases.

## Scope

This prototype proves ORM models, schema, relationships, audit, and transactions. It does not include the old Analysis pipeline or any migration of real inventory. Generic cross-domain provenance links are validated at the application level rather than by SQL foreign keys.
