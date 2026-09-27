"""Shared exception types for NetVoyager packages.

All application-defined exceptions inherit from NetVoyagerError to provide
consistent error codes, messages, and structured context.

Domain-specific exceptions belong in their owning packages and inherit from
these core types. Callers decide how to handle and log failures; exceptions
do not log themselves.
"""

from __future__ import annotations

from typing import Any


class NetVoyagerError(Exception):
    """Base exception for application-defined NetVoyager failures.

    Each error carries:
    - code: a stable identifier for programmatic handling
    - message: a human-readable explanation of the failure
    - details: structured context describing the affected operation or data
    - status_code: optional HTTP status metadata for API integrations

    Core and domain code normally leave status_code unset. CLI applications
    and API handlers decide how to present the error to their callers.

    Details should contain JSON-compatible values when used in structured
    output. This class does not validate or convert those values.
    """

    def __init__(
        self,
        *,
        code: str,
        message: str,
        details: dict[str, object] | None = None,
        status_code: int | None = None,
    ) -> None:
        """Initialize an error with a consistent application-wide structure.

        The details dictionary is shallow-copied so subsequent changes to
        the caller's top-level dictionary do not change this exception.
        Nested mutable values remain shared.

        The message is also passed to Exception so str(error) returns the
        same human-readable explanation.
        """
        self.code = code
        self.message = message
        self.details: dict[str, object] = (
            dict(details) if details is not None else {}
        )
        self.status_code = status_code

        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        """Return a structured representation for CLI or API handling.

        The result always includes code, message, and details. The
        status_code field is included only when explicitly assigned.

        Details are shallow-copied into the result. This method does not
        serialize arbitrary objects, redact sensitive values, or include
        traceback information. Callers control what is exposed externally.
        """
        payload: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
            "details": dict(self.details),
        }

        if self.status_code is not None:
            payload["status_code"] = self.status_code

        return payload


class NetVoyagerConfigError(NetVoyagerError):
    """Raised when application configuration prevents an operation.

    Use this for missing required settings, invalid configuration values,
    or incompatible configuration combinations.

    Callers provide a specific error code and relevant context. Invalid
    records in an imported inventory are handled by the importing package,
    rather than classified as application configuration failures.
    """


class NetVoyagerInvariantError(NetVoyagerError):
    """Raised when an internal consistency rule is unexpectedly violated.

    Use this when application state breaks an assumption that should have
    been maintained by the implementation or earlier validation.

    An invariant failure normally requires investigation. Expected input
    errors and routine duplicate records should use their own specific
    exception types.
    """
