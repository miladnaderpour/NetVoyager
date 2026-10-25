"""Repository for Location ORM entities."""
from .base import Repository
from ..models import Location


class LocationRepository(Repository):
    def __init__(self, session):
        super().__init__(session, Location)
