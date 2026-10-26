from datetime import datetime, timezone
import pytest
from pydantic import ValidationError
from netvoyager_schemas.imports import (
    SourceDataset, ImportDevice, ImportInterface, ImportNetworkPrefix,
    ImportAutonomousSystem, ImportLocation, ImportRelationship,
)

def test_full_mixed_dataset_roundtrip():
    dataset = SourceDataset(
        source_id="source-1", collected_at=datetime(2026, 10, 26, tzinfo=timezone.utc),
        devices=(ImportDevice(source_object_id="d1", serial="SERIAL-1"),),
        interfaces=(ImportInterface(device_ref="d1", name=" Gi1/0/1 "),),
        prefixes=(ImportNetworkPrefix(cidr="192.0.2.5/24", address_space="branch"),),
        autonomous_systems=(ImportAutonomousSystem(asn=65010),),
        locations=(ImportLocation(code="SITE-A", parent_ref="REGION-A"),),
        relationships=(ImportRelationship(relationship_type="interface_connection", source_ref="p1", target_ref="p2"),),
    )
    assert dataset.interfaces[0].name == "Gi1/0/1"
    assert dataset.prefixes[0].cidr == "192.0.2.5/24"  # source evidence retained
    restored = SourceDataset.model_validate_json(dataset.model_dump_json())
    assert restored == dataset

def test_device_only_backwards_compatible():
    ds = SourceDataset(source_id="x", collected_at=datetime.now(timezone.utc), devices=(ImportDevice(name="a"),))
    assert ds.interfaces == ds.prefixes == ds.autonomous_systems == ds.locations == ds.relationships == ()

@pytest.mark.parametrize("cidr", ["192.0.2.0/24", "2001:db8::1/64"])
def test_valid_prefix(cidr):
    assert ImportNetworkPrefix(cidr=cidr).cidr == cidr

@pytest.mark.parametrize("cidr", ["garbage", "192.0.2.0/33", "2001:db8::/129"])
def test_invalid_prefix(cidr):
    with pytest.raises(ValidationError): ImportNetworkPrefix(cidr=cidr)

@pytest.mark.parametrize("vlan", [0, 4095, -1])
def test_invalid_vlan(vlan):
    with pytest.raises(ValidationError): ImportNetworkPrefix(cidr="10.0.0.0/8", vlan=vlan)

@pytest.mark.parametrize("asn", [-1, 4294967296])
def test_invalid_asn(asn):
    with pytest.raises(ValidationError): ImportAutonomousSystem(asn=asn)

def test_valid_asn32():
    assert ImportAutonomousSystem(asn=4200000000).asn == 4200000000

def test_interface_requires_name():
    with pytest.raises(ValidationError): ImportInterface(name="  ")

def test_relationship_rejects_unknown_kind():
    with pytest.raises(ValidationError): ImportRelationship(relationship_type="other", source_ref="a", target_ref="b")

def test_relationship_rejects_blank_refs():
    with pytest.raises(ValidationError): ImportRelationship(relationship_type="device_connection", source_ref="  ", target_ref="b")

def test_imports_reject_lifecycle_field():
    with pytest.raises(ValidationError): ImportLocation(code="A", record_type="canonical")

def test_independent_default_source_attributes():
    a = ImportInterface(name="a")
    b = ImportInterface(name="b")
    a.source_attributes["x"] = 1
    assert b.source_attributes == {}
