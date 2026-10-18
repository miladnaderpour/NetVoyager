
"""Database and repository exceptions using NetVoyager error conventions.

Exceptions inherit Core's structured error contract and do not log themselves.
"""

from netvoyager_core.exceptions import NetVoyagerError


class NetVoyagerDatabaseError(NetVoyagerError):
    """Base exception for SQL database infrastructure failures."""


class DatabaseConfigurationError(NetVoyagerDatabaseError):
    """Raised when database configuration prevents initialization."""


class DatabaseTransactionError(NetVoyagerDatabaseError):
    """Raised when a database transaction cannot be completed."""


class NetVoyagerStorageError(NetVoyagerError):
    """Base exception for repository and storage failures."""


class RepositoryConflictError(NetVoyagerStorageError):
    """Raised when a repository operation conflicts with stored data."""


class RepositoryNotFoundError(NetVoyagerStorageError):
    """Raised when a required repository object does not exist."""


class TransactionError(NetVoyagerStorageError):
    """Raised when a Unit of Work transaction cannot be completed."""
