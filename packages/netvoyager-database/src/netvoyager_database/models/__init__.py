"""Import all ORM models so Alembic sees the complete metadata."""
from .base import Base, InventoryRecord, new_id, now_utc, RelationMixin
from .location import Location
from .network_prefix import NetworkPrefix
from .device import Device
from .autonomous_system import AutonomousSystem
from .interface import Interface
from .address_space import AddressSpace
from .relationships import *
from .history import *

from . import relationship_validation as _relationship_validation
