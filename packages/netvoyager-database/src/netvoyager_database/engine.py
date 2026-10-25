"""Engine and session creation, never creates schema implicitly."""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker


def create_engine_and_session_factory(url: str):
    engine = create_engine(url, future=True)
    if url.startswith('sqlite'):
        @event.listens_for(engine, 'connect')
        def _foreign_keys(connection, _):
            cursor = connection.cursor()
            cursor.execute('PRAGMA foreign_keys=ON')
            cursor.close()
    return engine, sessionmaker(bind=engine, expire_on_commit=False, future=True)
