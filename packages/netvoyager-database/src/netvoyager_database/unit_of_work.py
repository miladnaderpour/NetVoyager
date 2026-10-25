"""Small transaction boundary, with no domain policy embedded."""
from __future__ import annotations
from sqlalchemy.orm import Session
from .repositories import DeviceRepository, LocationRepository, NetworkPrefixRepository, AutonomousSystemRepository, InterfaceRepository


class UnitOfWork:
    def __init__(self, session_factory):
        self._factory = session_factory
        self.session: Session | None = None
        self._committed = False

    def __enter__(self):
        self.session = self._factory()
        self.devices = DeviceRepository(self.session)
        self.locations = LocationRepository(self.session)
        self.network_prefixes = NetworkPrefixRepository(self.session)
        self.autonomous_systems = AutonomousSystemRepository(self.session)
        self.interfaces = InterfaceRepository(self.session)
        return self

    def commit(self):
        if self.session is None:
            raise RuntimeError('UnitOfWork not active')
        self.session.commit()
        self._committed = True

    def __exit__(self, exc_type, exc, tb):
        if self.session is not None:
            if not self._committed:
                self.session.rollback()
            self.session.close()
            self.session = None
        return False
