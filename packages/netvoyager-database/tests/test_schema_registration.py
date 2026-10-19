
"""Verify registration of database and intelligence SQLAlchemy models."""

from sqlalchemy import create_engine, inspect

from netvoyager_database.schema import create_schema, get_schema_metadata


def test_schema_registers_database_and_intelligence_models() -> None:
    """Register all expected tables in their owning metadata."""
    database_metadata, intelligence_metadata = get_schema_metadata()

    assert database_metadata is not intelligence_metadata

    assert {
        "network_devices",
        "device_discovery_candidates",
        "device_discovery_relationships",
    }.issubset(database_metadata.tables)

    assert {
        "evidence_records",
        "evidence_relations",
        "findings",
    }.issubset(intelligence_metadata.tables)


def test_create_schema_creates_both_model_families() -> None:
    """Create database and intelligence tables in one database."""
    engine = create_engine("sqlite+pysqlite:///:memory:")

    try:
        create_schema(engine)

        table_names = set(inspect(engine).get_table_names())

        assert {
            "network_devices",
            "device_discovery_candidates",
            "device_discovery_relationships",
            "evidence_records",
            "evidence_relations",
            "findings",
        }.issubset(table_names)

        # Calling schema initialization again must be safe.
        create_schema(engine)

    finally:
        engine.dispose()
