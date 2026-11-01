"""V1 standardized dataset contract and unverified inventory name semantics."""
from datetime import datetime, timezone
from pathlib import Path
from openpyxl import Workbook
from netvoyager_schemas.imports import SourceDataset
from netvoyager_import.inventory.excel import read_network_devices


def test_inventory_returns_source_neutral_dataset(tmp_path: Path):
    w=Workbook(); s=w.active
    s.append(['name','host_name','site','management_ip','serial_number'])
    s.append(['INVENTORY-LABEL','unverified-host','S1','192.0.2.10','SER-1'])
    path=tmp_path/'inventory.xlsx';w.save(path);w.close()
    dataset=read_network_devices(path,collected_at=datetime(2026,11,1,tzinfo=timezone.utc))
    assert isinstance(dataset,SourceDataset)
    assert len(dataset.devices)==1
    d=dataset.devices[0]
    assert d.name is None
    assert d.source_attributes['host_name']=='unverified-host'
    assert d.source_attributes['inventory_name']=='INVENTORY-LABEL'
    assert d.source_object_id=='row:2'
