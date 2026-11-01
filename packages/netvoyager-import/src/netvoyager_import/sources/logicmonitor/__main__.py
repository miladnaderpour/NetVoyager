"""CLI: python -m netvoyager_import.sources.logicmonitor FILE --collected-at ..."""
import argparse
import csv
import json
from datetime import datetime
from pathlib import Path
from .excel import read_logicmonitor_excel


def main() -> None:
    parser = argparse.ArgumentParser(description="Import normalized LogicMonitor Excel inventory")
    parser.add_argument("workbook", type=Path)
    parser.add_argument("--collected-at", required=True, help="Actual collection date/time (ISO 8601 with timezone)")
    parser.add_argument("--output-dir", type=Path, default=Path("output/logicmonitor"))
    args = parser.parse_args()
    result = read_logicmonitor_excel(args.workbook, collected_at=datetime.fromisoformat(args.collected_at.replace("Z", "+00:00")))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "logicmonitor_dataset.json").write_text(result.dataset.model_dump_json(indent=2), encoding="utf-8")
    (args.output_dir / "logicmonitor_import_report.json").write_text(json.dumps(result.report(), indent=2, default=str), encoding="utf-8")
    with (args.output_dir / "logicmonitor_rejected_rows.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["excel_row", "source_excel_row", "severity", "code", "message"])
        writer.writeheader()
        for issue in result.issues:
            if issue.severity == "error":
                writer.writerow(issue.as_dict())
    print(f"Rows: {result.total_rows}; imported: {len(result.dataset.devices)}; rejected: {result.rejected_rows}; issues: {len(result.issues)}")
    print(f"Outputs: {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
