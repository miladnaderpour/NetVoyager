
"""SQLAlchemy metadata registration for NetVoyager persistence.

Database-owned entities and Intelligence-owned models retain separate
declarative bases. Schema management registers both model families.
"""

from sqlalchemy import Engine, MetaData

from netvoyager_database.entities import (
    DeviceDiscoveryCandidateEntity,
    DeviceDiscoveryRelationshipEntity,
    NetworkDeviceEntity,
)
from netvoyager_database.entities.base import Base
from netvoyager_intelligence.base import IntelligenceBase
from netvoyager_intelligence.evidence import (
    EvidenceRecord,
    EvidenceRelation,
)
from netvoyager_intelligence.findings import Finding


def get_schema_metadata() -> tuple[MetaData, MetaData]:
    """Return the registered metadata for both model families."""
    return Base.metadata, IntelligenceBase.metadata


def create_schema(engine: Engine) -> None:
    """Create database-owned and intelligence-owned tables."""
    for metadata in get_schema_metadata():
        metadata.create_all(engine)
