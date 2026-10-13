
"""Shared physical device models independent of vendor and inventory source.

Each network device has a deterministic UUIDv5 identity derived from its
imported name. Importers are responsible for providing unique names.

Device state is identified separately using a deterministic UUIDv5
derived from selected technical attributes. Integration-specific
metadata is managed independently and excluded from state identity.
"""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass, field
from ipaddress import IPv4Address
from typing import ClassVar
from uuid import UUID, uuid5

from netvoyager_core.exceptions import NetVoyagerError
from netvoyager_core.types import JsonValue as JsonValue


NETWORK_DEVICE_NAMESPACE = UUID(
    "fd51f149-4c34-4915-9b10-b72e3e1151a9"
)

NETWORK_DEVICE_STATE_NAMESPACE = UUID(
    "912d70e1-f1d3-4937-8e4e-78c9489ca119"
)


@dataclass(slots=True)
class NetworkDevice:
    """A physical network device with deterministic identity and state.

    The device_id is generated from the imported name and remains
    unchanged throughout the object's lifetime.

    The name is an identity field and cannot be modified after
    initialization. Renaming a device requires establishing a new
    identity under the current naming strategy.

    The state_id is calculated from device_id and selected technical
    attributes. Changes to these attributes produce a new state UUID
    without changing the device identity.

    Serial numbers, management addresses, and hardware information
    belong to device state rather than identity.

    Integration-specific attributes belong in metadata namespaces.
    Metadata is excluded from state calculation and exposed through
    detached snapshots to prevent accidental external modification.

    Type annotations describe expected values but do not perform
    runtime validation or conversion.
    """

    STATE_FIELDS: ClassVar[tuple[str, ...]] = (
        "role",
        "site",
        "description",
        "primary_IPv4",
        "management_ip",
        "host_name",
        "virtual_chassis",
        "manufacturer",
        "model",
        "serial_number",
        "status",
        "asset_tag",
        "software_version",
    )

    name: str

    device_id: UUID = field(
        init=False,
        compare=True,
    )

    role: str | None = None
    site: str | None = None
    description: str | None = None

    primary_IPv4: IPv4Address | None = None
    management_ip: IPv4Address | None = None
    host_name: str | None = None

    virtual_chassis: str | None = None
    manufacturer: str | None = None
    model: str | None = None
    serial_number: str | None = None
    status: str | None = None
    asset_tag: str | None = None

    software_version: str | None = None

    _metadata: dict[str, dict[str, JsonValue]] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        """Generate the device UUIDv5 from its imported name."""
        object.__setattr__(
            self,
            "device_id",
            uuid5(
                NETWORK_DEVICE_NAMESPACE,
                f"network-device:{self.name}",
            ),
        )

    def __setattr__(self, name: str, value: object) -> None:
        """Prevent changes to identity fields after initialization."""
        if name in {"name", "device_id"} and hasattr(self, name):
            raise AttributeError(
                f"{name} cannot be modified after initialization."
            )

        object.__setattr__(self, name, value)

    @property
    def state_id(self) -> UUID:
        """Return a deterministic UUIDv5 for the current device state.

        The state includes the device identity and selected technical
        attributes. Each evaluation reflects the current field values.

        Integration metadata does not participate in state identity.
        """
        state = {
            field_name: (
                str(value)
                if isinstance(value, IPv4Address)
                else value
            )
            for field_name in self.STATE_FIELDS
            for value in (getattr(self, field_name),)
        }

        payload = json.dumps(
            {
                "schema": "network-device-state-v1",
                "device_id": str(self.device_id),
                "state": state,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

        return uuid5(
            NETWORK_DEVICE_STATE_NAMESPACE,
            payload,
        )

    def update_metadata(
        self,
        namespace: str,
        values: dict[str, JsonValue],
    ) -> None:
        """Add or update metadata keys within an integration namespace.

        A missing namespace is created. Supplied keys overwrite matching
        keys, while other existing keys remain unchanged. Nested values
        are replaced as whole values rather than recursively merged.

        Values are deep-copied before storage to isolate the device from
        later changes to the caller's dictionaries or lists.

        An invalid namespace raises NetVoyagerError. It must be a
        nonempty string without surrounding whitespace. Callers must
        supply JSON-compatible values; this method does not validate
        or serialize arbitrary Python objects.
        """
        self._validate_namespace(namespace)
        copied_values = deepcopy(values)
        self._metadata.setdefault(namespace, {}).update(copied_values)

    def get_metadata(self, namespace: str) -> dict[str, JsonValue]:
        """Return a detached snapshot of one metadata namespace.

        A missing namespace returns an empty dictionary. Modifying the
        returned dictionary or its nested values does not change the
        device. Use update_metadata() to apply changes explicitly.
        """
        self._validate_namespace(namespace)
        return deepcopy(self._metadata.get(namespace, {}))

    def remove_metadata(self, namespace: str) -> None:
        """Remove an entire metadata namespace if it exists.

        A missing namespace leaves the device unchanged. Removing an
        integration namespace does not affect explicit device fields.
        """
        self._validate_namespace(namespace)
        self._metadata.pop(namespace, None)

    @property
    def metadata(self) -> dict[str, dict[str, JsonValue]]:
        """Return a detached snapshot of all metadata namespaces.

        The snapshot includes independent copies of nested dictionaries
        and lists. Later changes to either the device or the returned
        snapshot do not affect the other.
        """
        return deepcopy(self._metadata)

    @staticmethod
    def _validate_namespace(namespace: str) -> None:
        """Reject invalid integration metadata namespace names.

        Namespace names must be nonempty strings without surrounding
        whitespace. Names are case-sensitive and are not normalized.
        Integrations should consistently use lowercase names.
        """
        if (
            not isinstance(namespace, str)
            or not namespace.strip()
            or namespace != namespace.strip()
        ):
            raise NetVoyagerError(
                code="device.invalid_metadata_namespace",
                message=(
                    "Metadata namespace must be a nonempty string "
                    "without surrounding whitespace."
                ),
            )
