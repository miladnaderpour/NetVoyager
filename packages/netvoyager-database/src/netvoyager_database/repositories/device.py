"""Repository for Device ORM entities."""
from .base import Repository
from ..models import Device


class DeviceRepository(Repository):
    def __init__(self, session):
        super().__init__(session, Device)
