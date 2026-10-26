from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from netvoyager_schemas.imports import ImportDevice, SourceDataset


def test_source_dataset_parses_nested_devices():
    dataset = SourceDataset.model_validate({
        "source_id": " meraki-dashboard ",
        "collected_at": "2026-10-26T12:00:00Z",
        "devices": [{"serial": " Q2XX-TEST-0001 ", "name": "switch-a", "management_ip": "192.0.2.10"}],
    })
    assert dataset.source_id == "meraki-dashboard"
    assert dataset.devices[0].serial == "Q2XX-TEST-0001"
    assert str(dataset.devices[0].management_ip) == "192.0.2.10"


def test_invalid_management_ip_is_rejected():
    with pytest.raises(ValidationError):
        ImportDevice(management_ip="not-an-ip")


def test_unknown_fields_are_rejected():
    with pytest.raises(ValidationError):
        ImportDevice(serial="TEST", record_type="canonical")


def test_blank_source_id_is_rejected():
    with pytest.raises(ValidationError):
        SourceDataset(source_id="  ", collected_at=datetime.now(timezone.utc))


def test_naive_collection_time_is_rejected():
    with pytest.raises(ValidationError):
        SourceDataset(source_id="source-a", collected_at=datetime(2026, 10, 26))


def test_dataset_serializes_to_json():
    dataset = SourceDataset(source_id="source-a", collected_at=datetime.now(timezone.utc), devices=(ImportDevice(serial="TEST"),))
    assert SourceDataset.model_validate_json(dataset.model_dump_json()).devices[0].serial == "TEST"


def test_devices_default_is_empty():
    dataset = SourceDataset(source_id="source-a", collected_at=datetime.now(timezone.utc))
    assert dataset.devices == ()


def test_source_specific_attributes_are_preserved():
    device = ImportDevice(source_object_id="id-1", source_attributes={"networkId": "N_TEST"})
    assert device.source_attributes["networkId"] == "N_TEST"
