from datetime import datetime, timezone
from openpyxl import Workbook
import pytest
from netvoyager_import.sources.logicmonitor import read_logicmonitor_excel

COLS = ["Resource Name", "Source Excel Row", "Normalized Name", "Normalized Management IP", "Normalized Serial", "Review Status", "Review Issues", "Original Resource Name"]


def workbook(tmp_path, rows):
    p = tmp_path / "normalized.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "Inventory"
    ws.append(COLS)
    for row in rows:
        ws.append(row)
    wb.save(p)
    return p


def read(path):
    return read_logicmonitor_excel(path, collected_at=datetime(2026, 10, 27, tzinfo=timezone.utc))


def test_valid_with_provenance(tmp_path):
    p = workbook(tmp_path, [["core", 2, "core", "10.0.0.10", "000123", "READY", None, "core - 10.0.0.10"]])
    result = read(p)
    assert (result.total_rows, result.rejected_rows) == (1, 0)
    d = result.dataset.devices[0]
    assert d.serial == "000123"
    assert d.observation_method == "nms"
    assert str(d.management_ip) == "10.0.0.10"
    assert d.source_attributes["Original Resource Name"] == "core - 10.0.0.10"
    assert d.source_object_id == "row:2"


def test_missing_serial_is_kept(tmp_path):
    p = workbook(tmp_path, [["core", 2, "core", "10.0.0.10", None, "REVIEW", "MISSING_SERIAL", "core"]])
    result = read(p)
    assert len(result.dataset.devices) == 1
    assert result.dataset.devices[0].serial is None
    assert {i.code for i in result.issues} == {"SOURCE_REVIEW", "MISSING_SERIAL"}


def test_bad_ip_does_not_discard_name(tmp_path):
    p = workbook(tmp_path, [["core", 2, "core", "not-an-ip", "XYZ", "REVIEW", "BAD_IP", "core"]])
    result = read(p)
    assert len(result.dataset.devices) == 1
    assert result.dataset.devices[0].management_ip is None
    assert "INVALID_NORMALIZED_IP" in {i.code for i in result.issues}


def test_empty_identity_rejected(tmp_path):
    p = workbook(tmp_path, [["unknown", 2, None, None, None, "REVIEW", "NO_NAME", "unknown"]])
    result = read(p)
    assert result.rejected_rows == 1
    assert not result.dataset.devices


def test_duplicate_serial_rows_not_deduplicated(tmp_path):
    p = workbook(tmp_path, [["a", 2, "a", "10.0.0.1", "S1", "READY", None, "a"], ["b", 3, "b", "10.0.0.2", "S1", "REVIEW", "DUPLICATE_SERIAL", "b"]])
    result = read(p)
    assert len(result.dataset.devices) == 2
    assert result.dataset.devices[0].serial == result.dataset.devices[1].serial


def test_requires_timezone(tmp_path):
    p = workbook(tmp_path, [])
    with pytest.raises(ValueError, match="timezone"):
        read_logicmonitor_excel(p, collected_at=datetime(2026, 10, 27))
