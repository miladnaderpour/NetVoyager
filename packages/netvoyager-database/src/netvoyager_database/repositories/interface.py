"""Repository for Interface ORM entities."""
from .base import Repository
from ..models import Interface


class InterfaceRepository(Repository):
    def __init__(self, session):
        super().__init__(session, Interface)
