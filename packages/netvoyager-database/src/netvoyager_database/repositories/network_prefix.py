"""Repository for NetworkPrefix ORM entities."""
from .base import Repository
from ..models import NetworkPrefix


class NetworkPrefixRepository(Repository):
    def __init__(self, session):
        super().__init__(session, NetworkPrefix)
