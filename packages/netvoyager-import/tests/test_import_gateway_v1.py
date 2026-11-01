from datetime import datetime
from pathlib import Path
import pytest
from netvoyager_import import import_data
from netvoyager_import.gateway import ImportGatewayError
from netvoyager_import.inventory.excel import InventoryImportError

STAMP = datetime.fromisoformat('2026-11-01T12:00:00+01:00')
BOOK = Path(__file__).parents[5] / '4sInventory(2).xlsx'

@pytest.fixture
def sample_book(tmp_path):
    from openpyxl import Workbook
    wb=Workbook(); sheet=wb.active
    sheet.append(['name','site','management_ip','serial_number','model'])
    sheet.append(['LABEL-A','SITE1','10.1.1.1','SER-1','X'])
    sheet.append(['LABEL-B','SITE1','10.1.1.1','SER-2','X'])
    sheet.append(['LABEL-A','SITE2','10.1.1.2','SER-1','Y'])
    file=tmp_path/'inventory.xlsx';wb.save(file);wb.close();return file

def test_all_rows_preserved_and_duplicates_reported(sample_book):
    result=import_data(source_type='inventory_excel',file_path=sample_book,collected_at=STAMP)
    assert len(result.dataset.devices)==3
    assert result.statistics.total_rows==3
    assert result.statistics.duplicate_serial_groups==1
    assert result.statistics.shared_management_ip_groups==1
    assert [d.source_attributes['inventory_name'] for d in result.dataset.devices]==['LABEL-A','LABEL-B','LABEL-A']
    assert all(d.name is None for d in result.dataset.devices)
    assert {i.code for i in result.issues}=={'DUPLICATE_SERIAL','SHARED_MANAGEMENT_IP'}

def test_no_naming_or_canonical_assumptions(sample_book):
    result=import_data(source_type='inventory_excel',file_path=sample_book,collected_at=STAMP)
    assert [str(d.management_ip) for d in result.dataset.devices]==['10.1.1.1','10.1.1.1','10.1.1.2']
    assert [d.serial for d in result.dataset.devices]==['SER-1','SER-2','SER-1']
    assert [d.source_object_id for d in result.dataset.devices]==['row:2','row:3','row:4']

def test_invalid_cell_does_not_drop_row(tmp_path):
    from openpyxl import Workbook
    wb=Workbook();ws=wb.active;ws.append(['name','site','management_ip','serial_number']);ws.append(['bad','SITE','invalid','unknown']); p=tmp_path/'bad.xlsx';wb.save(p);wb.close()
    result=import_data(source_type='inventory_excel',file_path=p,collected_at=STAMP)
    assert len(result.dataset.devices)==1
    assert result.dataset.devices[0].management_ip is None
    assert result.dataset.devices[0].source_attributes['management_ip']=='invalid'
    assert {'INVALID_MANAGEMENT_IP','UNUSABLE_SERIAL','MISSING_SERIAL'} <= {i.code for i in result.issues}

def test_fatal_columns(sample_book,tmp_path):
    from openpyxl import Workbook
    wb=Workbook();ws=wb.active;ws.append(['name']); p=tmp_path/'empty.xlsx';wb.save(p);wb.close()
    with pytest.raises(InventoryImportError) as exc:
        import_data(source_type='inventory_excel',file_path=p,collected_at=STAMP)
    assert exc.value.code=='import.missing_columns'

def test_bad_source_and_inputs(sample_book):
    with pytest.raises(ImportGatewayError):
        import_data(source_type='unknown',file_path=sample_book,collected_at=STAMP)
    with pytest.raises(ImportGatewayError):
        import_data(source_type='inventory_excel',file_path=sample_book,raw_data='raw',collected_at=STAMP)
    with pytest.raises(ImportGatewayError):
        import_data(source_type='inventory_excel',raw_data='raw',collected_at=STAMP)

def test_time_validation(sample_book):
    with pytest.raises(InventoryImportError):
        import_data(source_type='inventory_excel',file_path=sample_book,collected_at=datetime(2026,11,1))
