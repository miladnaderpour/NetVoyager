"""Scope-specific exceptions using the shared NetVoyager error structure."""

from ipaddress import IPv4Network

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
    """Raised when a prefix is already directly assigned to a scope.

    A duplicate means the exact same network address and prefix length.
    Overlapping networks with different prefix lengths remain distinct.

    Conflicts between different scopes require a collection-level check
    and are not handled by this exception.
    """

    def __init__(
        self,
        *,
        scope_id: str,
        prefix: IPv4Network,
    ) -> None:
        """Describe the duplicate assignment using JSON-compatible details."""
        self.scope_id = scope_id
        self.prefix = prefix

        super().__init__(
            code="scope.duplicate_prefix",
            message=(
                f"Prefix {prefix} is already assigned to scope {scope_id!r}."
            ),
            details={
                "scope_id": scope_id,
                "prefix": str(prefix),
            },
        )