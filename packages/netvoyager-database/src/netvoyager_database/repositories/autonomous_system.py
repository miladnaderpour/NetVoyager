"""Repository for AutonomousSystem ORM entities."""
from .base import Repository
from ..models import AutonomousSystem


class AutonomousSystemRepository(Repository):
    def __init__(self, session):
        super().__init__(session, AutonomousSystem)
