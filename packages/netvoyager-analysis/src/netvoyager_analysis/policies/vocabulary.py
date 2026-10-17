
"""Supported claims, actions, and validation requirements.

Policies may only authorize capabilities explicitly supported by
NetVoyager. Domain-specific validation is performed separately.
"""

SUPPORTED_CLAIMS = frozenset({
    "device.physical_identity",
    "device.name",
    "device.host_name",
    "device.display_name",
    "device.serial_number",
    "device.management_ip",
    "device.ip_address_observed",
    "device.model",
    "device.manufacturer",
    "device.software_version",
    "device.operational_status",
    "prefix.existence",
    "scope.existence",
    "relationship.device_site",
    "relationship.device_prefix",
    "relationship.prefix_site",
})

SUPPORTED_ACTIONS = frozenset({
    "record_observation",
    "create_candidate",
    "correlate_candidate",
    "promote_candidate",
    "create_canonical_device",
    "create_canonical_prefix",
    "create_canonical_scope",
    "propose_attribute",
    "confirm_attribute",
    "create_candidate_relationship",
    "infer_relationship",
    "validate_relationship",
})

SUPPORTED_REQUIREMENTS = frozenset({
    "unique_physical_serial",
    "unambiguous_device_match",
    "verified_device_identity",
    "explicit_management_interface",
    "verified_management_address",
    "approved_site_identity",
    "valid_network_prefix",
    "verified_reporting_source",
})


_ATTRIBUTE_ACTIONS = frozenset({
    "record_observation",
    "propose_attribute",
    "confirm_attribute",
})

_RELATIONSHIP_ACTIONS = frozenset({
    "record_observation",
    "create_candidate_relationship",
    "infer_relationship",
    "validate_relationship",
})


CLAIM_ACTIONS: dict[str, frozenset[str]] = {
    "device.physical_identity": frozenset({
        "record_observation",
        "create_candidate",
        "correlate_candidate",
        "promote_candidate",
        "create_canonical_device",
    }),
    "device.name": _ATTRIBUTE_ACTIONS,
    "device.host_name": _ATTRIBUTE_ACTIONS,
    "device.display_name": _ATTRIBUTE_ACTIONS,
    "device.serial_number": _ATTRIBUTE_ACTIONS,
    "device.management_ip": _ATTRIBUTE_ACTIONS,
    "device.ip_address_observed": frozenset({
        "record_observation",
        "correlate_candidate",
    }),
    "device.model": _ATTRIBUTE_ACTIONS,
    "device.manufacturer": _ATTRIBUTE_ACTIONS,
    "device.software_version": _ATTRIBUTE_ACTIONS,
    "device.operational_status": _ATTRIBUTE_ACTIONS,
    "prefix.existence": frozenset({
        "record_observation",
        "create_candidate",
        "create_canonical_prefix",
    }),
    "scope.existence": frozenset({
        "record_observation",
        "create_candidate",
        "create_canonical_scope",
    }),
    "relationship.device_site": _RELATIONSHIP_ACTIONS,
    "relationship.device_prefix": _RELATIONSHIP_ACTIONS,
    "relationship.prefix_site": _RELATIONSHIP_ACTIONS,
}
