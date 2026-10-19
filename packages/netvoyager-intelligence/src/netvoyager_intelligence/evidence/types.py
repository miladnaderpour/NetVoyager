
"""JSON serialization for supported evidence provenance values."""

from datetime import date, datetime
from ipaddress import (
    IPv4Address,
    IPv4Network,
    IPv6Address,
    IPv6Network,
    ip_address,
    ip_network,
)
from uuid import UUID

from sqlalchemy import JSON
from sqlalchemy.types import TypeDecorator


_TAG = "__netvoyager_type__"


def _encode(value: object) -> object:
    """Convert supported Python values into JSON-compatible values."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, UUID):
        return {_TAG: "uuid", "value": str(value)}

    if isinstance(value, (IPv4Address, IPv6Address)):
        return {_TAG: "ip_address", "value": str(value)}

    if isinstance(value, (IPv4Network, IPv6Network)):
        return {_TAG: "ip_network", "value": str(value)}

    if isinstance(value, datetime):
        return {_TAG: "datetime", "value": value.isoformat()}

    if isinstance(value, date):
        return {_TAG: "date", "value": value.isoformat()}

    if isinstance(value, tuple):
        return {
            _TAG: "tuple",
            "value": [_encode(item) for item in value],
        }

    if isinstance(value, list):
        return [_encode(item) for item in value]

    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("Evidence details require string dictionary keys.")

        if _TAG in value:
            raise ValueError(
                f"Evidence details reserve the key {_TAG!r}."
            )

        return {key: _encode(item) for key, item in value.items()}

    raise TypeError(
        f"Unsupported evidence detail value: {type(value).__name__}"
    )


def _decode(value: object) -> object:
    """Restore supported Python values from stored JSON."""
    if isinstance(value, list):
        return [_decode(item) for item in value]

    if not isinstance(value, dict):
        return value

    tag = value.get(_TAG)

    if tag is None:
        return {key: _decode(item) for key, item in value.items()}

    raw = value["value"]

    if tag == "uuid":
        return UUID(raw)

    if tag == "ip_address":
        return ip_address(raw)

    if tag == "ip_network":
        return ip_network(raw)

    if tag == "datetime":
        return datetime.fromisoformat(raw)

    if tag == "date":
        return date.fromisoformat(raw)

    if tag == "tuple":
        return tuple(_decode(item) for item in raw)

    raise ValueError(f"Unsupported evidence detail type: {tag}")


class EvidenceJSON(TypeDecorator):
    """Store supported provenance values in a JSON column.

    Values are encoded before persistence and restored on retrieval.
    JSON fields are not intended for indexed evidence searches.
    """

    impl = JSON
    cache_ok = True

    def process_bind_param(self, value, dialect):
        """Encode details before binding them to the database."""
        return None if value is None else _encode(value)

    def process_result_value(self, value, dialect):
        """Restore details after loading them from the database."""
        return None if value is None else _decode(value)
