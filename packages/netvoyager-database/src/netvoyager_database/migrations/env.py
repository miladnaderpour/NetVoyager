"""Alembic environment for isolated experimental schema."""
from alembic import context
from sqlalchemy import create_engine, pool
from netvoyager_database.models import Base
config=context.config
url=config.attributes.get('database_url') or config.get_main_option('sqlalchemy.url')
if not url:
    raise RuntimeError('A database URL is required')

def run():
    engine=create_engine(url,poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection,target_metadata=Base.metadata,render_as_batch=True,compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()
run()
