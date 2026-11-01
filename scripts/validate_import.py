"""Inspect a NetVoyager V1 import without writing to the NetVoyager database."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from netvoyager_import import import_data
from netvoyager_core.exceptions import NetVoyagerError


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a real inventory via the NetVoyager Import V1 gateway")
    parser.add_argument("file", type=Path, help="Excel file to import")
    parser.add_argument("--source-type", default="inventory_excel")
    parser.add_argument("--collected-at", required=True, help="Actual known export time, ISO 8601 with timezone offset")
    parser.add_argument("--output-dir", type=Path, default=Path("output/import-validation"))
    parser.add_argument("--expected-rows", type=int, default=None)
    args = parser.parse_args()

    collected_at = datetime.fromisoformat(args.collected_at.replace("Z", "+00:00"))
    if collected_at.tzinfo is None or collected_at.utcoffset() is None:
        parser.error("--collected-at must include an explicit timezone offset (e.g. +01:00 or Z)")

    try:
        result = import_data(source_type=args.source_type, file_path=args.file, collected_at=collected_at)
    except NetVoyagerError as exc:
        print(f"Import failed: {exc}")
        return 1

    stats = result.statistics.model_dump(mode="json")
    issues = [issue.model_dump(mode="json") for issue in result.issues]
    counts = Counter((issue["severity"], issue["code"]) for issue in issues)
    print("\nImport statistics")
    print(json.dumps(stats, indent=2))
    print("\nIssue summary (severity / code)")
    if counts:
        for (severity, code), count in sorted(counts.items()):
            print(f"  {severity:7} {code:30} {count}")
    else:
        print("  No issues")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "dataset.json").write_text(result.dataset.model_dump_json(indent=2), encoding="utf-8")
    report = {"source_type": args.source_type, "input_file": str(args.file),
              "statistics": stats, "issue_summary": [
                  {"severity": severity, "code": code, "count": count}
                  for (severity, code), count in sorted(counts.items())
              ], "issues": issues}
    (args.output_dir / "import_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nArtifacts: {args.output_dir.resolve()}")

    if args.expected_rows is not None and (stats["total_rows"] != args.expected_rows or stats["imported_rows"] != args.expected_rows or stats["rejected_rows"] != 0):
        print(f"FAIL: expected {args.expected_rows} total and imported rows, with zero rejects")
        return 2
    print("PASS: import completed; see report for diagnostics")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
