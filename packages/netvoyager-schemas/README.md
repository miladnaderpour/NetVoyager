# netvoyager-schemas

Shared Pydantic v2 contracts, independent of SQLAlchemy and Analysis.

## Import contract V1 baseline

`netvoyager_schemas.imports` provides `SourceDataset`, `ImportDevice`,
`ImportInterface`, `ImportNetworkPrefix`, `ImportAutonomousSystem`,
`ImportLocation`, and `ImportRelationship`.

- `ImportDevice` is unchanged from Schemas V1.
- `SourceDataset` keeps its original fields and adds optional tuple collections.
- Import contracts report **source facts**, not canonical database identity.
- `source_object_id`, `device_ref`, `parent_ref`, `source_ref`, `target_ref` are
  references supplied by the originating source. Analysis owns their resolution.
- The relationship kind selects one of the eight database association categories;
  the optional `relation` describes its meaning (e.g., `member_of`).
- CIDR strings are validated but left as reported. Network identity normalization
  belongs to the database/analysis lifecycle.
- `source_attributes` carries source-specific unmapped fields.
- Pydantic `frozen=True` prevents field reassignment; it does *not* deeply freeze
  nested dictionaries. Do not treat these schemas as security boundaries.

The V1 contracts form a stable baseline, **not a prohibition on future additive or
necessary breaking changes**. Update them with tests and version/migration plans
when real adapters or API consumers reveal new requirements.

## Test

`python -m pytest packages/netvoyager-schemas/tests -v --import-mode=importlib`
