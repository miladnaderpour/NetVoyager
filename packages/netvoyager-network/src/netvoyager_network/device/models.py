"""Shared device models independent of vendor and inventory source.

Each device has an internal UUID that remains stable across attribute
changes and must be preserved when saving and restoring the device.

Common device attributes are explicit fields. Integration-specific
attributes are stored in namespaced metadata so importers can enrich
a device without requiring a separate model for each source.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from ipaddress import IPv4Address
from typing import TypeAlias
from uuid import UUID, uuid4

from netvoyager_core.exceptions import NetVoyagerError
from netvoyager_core.types import JsonValue as JsonValue

@dataclass(slots=True)
class NetworkDevice:
    """A mutable network device with a stable internal identifier.

    device_id identifies the device independently of its name, addresses,
    serial number, and other attributes. A new UUID is generated when
    device_id is omitted. Supply the existing UUID when restoring a device.

    Treat device_id as immutable after creation. This convention is not
    enforced by the dataclass. Persistence code must save and restore it;
    importers must reuse an existing identity when reconciling records.

    UUID generation does not detect duplicate devices. Two independently
    constructed devices receive different IDs even when their attributes
    match. Importers are responsible for matching device identity and
    deciding whether existing attribute values should be replaced.

    Dataclass equality compares all fields, including device_id. Compare
    device_id explicitly when checking whether objects represent the same
    internal identity.

    Integration-specific attributes belong in metadata namespaces such as
    "meraki". Metadata is managed through methods and exposed as a detached
    snapshot so callers cannot accidentally modify internal nested values.

    Type annotations describe expected values; they do not perform runtime
    validation or conversion. Callers restoring an ID from text must convert
    it to UUID before constructing the device.
    """

    name: str

    device_id: UUID = field(
        default_factory=uuid4,
        kw_only=True,
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

        An invalid namespace raises NetVoyagerError. It must be a nonempty
        string without surrounding whitespace. Callers must supply
        JSON-compatible values; this method does not validate or serialize
        arbitrary Python objects.
        """
        self._validate_namespace(namespace)
        copied_values = deepcopy(values)
        self._metadata.setdefault(namespace, {}).update(copied_values)

    def get_metadata(self, namespace: str) -> dict[str, JsonValue]:
        """Return a detached snapshot of one metadata namespace.

        A missing namespace returns an empty dictionary. Modifying the
        returned dictionary or its nested values does not change the device.
        Use update_metadata() to apply changes explicitly.
        """
        self._validate_namespace(namespace)
        return deepcopy(self._metadata.get(namespace, {}))

    def remove_metadata(self, namespace: str) -> None:
        """Remove an entire metadata namespace if it exists.

        A missing namespace leaves the device unchanged. This operation
        removes only integration metadata; explicit device fields such as
        software_version and serial_number are unaffected.
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
        """Reject namespace names that cannot identify an integration.

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