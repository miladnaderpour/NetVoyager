# netvoyager-import

Source-specific adapters produce `netvoyager_schemas.imports.SourceDataset` without writing to the database or making lifecycle decisions.

## LogicMonitor normalized Excel V1

Input must be created by the separate `normalize_logicmonitor.py` preparation utility and include the `Inventory` sheet and normalized column headers. Every source row is retained as its own `ImportDevice`, including missing serials, duplicate serials, and review flags when a usable name, serial, or IP is present.

```powershell
python -m pip install -e "./packages/netvoyager-schemas"
python -m pip install -e "./packages/netvoyager-import[test]"
python -m netvoyager_import.sources.logicmonitor `
  .\lm_Inventory_normalized.xlsx `
  --collected-at "2026-10-27T12:00:00+01:00" `
  --output-dir .\output\logicmonitor
```

**Replace `--collected-at` with the actual collection/export timestamp.** A date in the example is not an assertion about the uploaded file. We don't infer collection time from file modification timestamps.

Outputs:
- `logicmonitor_dataset.json`: validated Pydantic dataset
- `logicmonitor_import_report.json`: counts and row-level warnings/errors
- `logicmonitor_rejected_rows.csv`: unrecoverable rows only

`source_object_id=row:<Source Excel Row>` identifies rows **within that export only**, not permanent LogicMonitor device IDs. `source_attributes` preserves source fields and review flags. Each `ImportDevice` uses `observation_method="nms"`.

Importer does not deduplicate devices, create stack members, infer models from OS versions, or promote canonical records. The old `inventory/excel.py` is legacy and is not used by this adapter.
