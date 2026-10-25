"""Minimal generic repository mechanics (authorization lives in Analysis)."""
from sqlalchemy import select


class Repository:
    def __init__(self, session, model):
        self.session, self.model = session, model

    def add(self, entity):
        self.session.add(entity)
        self.session.flush()
        return entity

    def get(self, identifier):
        return self.session.get(self.model, identifier)

    def all(self):
        return tuple(self.session.scalars(select(self.model)).all())
