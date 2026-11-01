"""V1 duplicate coverage, preserving source records without identity decisions."""
from datetime import datetime, timezone
from pathlib import Path
from openpyxl import Workbook
from netvoyager_import.inventory.excel import read_excel_inventory

STAMP = datetime(2026,11,1,tzinfo=timezone.utc)

def test_duplicate_serial_and_shared_management_ip(tmp_path: Path):
    w=Workbook(); s=w.active
    s.append(['name','site','management_ip','serial_number'])
    s.append(['SW-A','SiteA','10.0.0.1','SER1'])
    s.append(['SW-A','SiteA','10.0.0.1','SER2'])
    s.append(['SW-B','SiteA','10.0.0.2','SER1'])
    path=tmp_path/'inventory.xlsx';w.save(path);w.close()
    r=read_excel_inventory(path,collected_at=STAMP)
    assert len(r.dataset.devices)==3
    assert [d.source_attributes['name'] for d in r.dataset.devices]==['SW-A','SW-A','SW-B']
    assert r.statistics.duplicate_serial_groups==1
    assert r.statistics.shared_management_ip_groups==1
    assert r.statistics.rejected_rows==0
