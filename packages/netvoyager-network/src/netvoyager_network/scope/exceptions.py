# netwoyager-network/netvoyager_network/scope/exceptions.py
"""Scope-specific exceptions using the shared NetVoyager error structure."""

from uuid import UUID

from netvoyager_core.exceptions import NetVoyagerError


class DuplicateScopeAsnError(NetVoyagerError):
    """Raised when an ASN is already directly associated with a scope.

    This checks membership within one scope. The same ASN may legitimately
    be associated with other scopes, including parents or children.
    """

    def __init__(self, *, scope_id: str, asn: int) -> None:
        """Describe the duplicate association using structured context."""
        self.scope_id = scope_id
        self.asn = asn

        super().__init__(
            code="scope.duplicate_asn",
            message=f"AS {asn} is already associated with scope {scope_id!r}.",
            details={
                "scope_id": scope_id,
                "asn": asn,
            },
        )


class DuplicateScopePrefixError(NetVoyagerError):
    """Raised when a network prefix ID is already associated with a scope.

    A duplicate means the same prefix UUID is already present.

    Exact CIDR duplicates and conflicts between different scopes require
    collection-level checks and are not handled by this exception.
    """

    def __init__(
        self,
        *,
        scope_id: str,
        prefix_id: UUID,
    ) -> None:
        """Describe the duplicate association using structured context."""
        self.scope_id = scope_id
        self.prefix_id = prefix_id

        super().__init__(
            code="scope.duplicate_prefix",
            message=(
                f"Prefix {prefix_id} is already associated "
                f"with scope {scope_id!r}."
            ),
            details={
                "scope_id": scope_id,
                "prefix_id": str(prefix_id),
            },
        )

class DuplicateScopeDeviceError(NetVoyagerError):
    """Raised when a device ID is already directly associated with a scope.

    Membership is checked by device_id, regardless of whether the caller
    supplies the same object or another object with that ID.

    This does not detect physical duplicates with different device IDs.
    The same device may be associated with other scopes.
    """

    def __init__(self, *, scope_id: str, device_id: UUID) -> None:
        """Describe the duplicate association using JSON-compatible details."""
        self.scope_id = scope_id
        self.device_id = device_id

        super().__init__(
            code="scope.duplicate_device",
            message=(
                f"Device {device_id} is already associated "
                f"with scope {scope_id!r}."
            ),
            details={
                "scope_id": scope_id,
                "device_id": str(device_id),
            },
        )