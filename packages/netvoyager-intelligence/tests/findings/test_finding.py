
"""Tests for SQLAlchemy-native analysis findings."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from netvoyager_intelligence.findings import Finding


def test_finding_generates_identity_and_timestamp() -> None:
    """Assign finding identity and timestamp before persistence."""
    finding = Finding(
        kind="prefix_multiple_sites",
        severity="warning",
        message="Prefix belongs to multiple sites.",
    )

    assert isinstance(finding.id, UUID)
    assert finding.created_at.tzinfo is not None
    assert finding.details == {}
    assert finding.object_id is None
    assert finding.object_type is None


def test_finding_preserves_explicit_identity() -> None:
    """Preserve an explicitly supplied finding identifier."""
    identifier = uuid4()

    finding = Finding(
        kind="identity_conflict",
        severity="error",
        message="Conflicting device identity.",
        id=identifier,
    )

    assert finding.id == identifier


def test_finding_round_trip(
    session_factory: sessionmaker[Session],
) -> None:
    """Persist and reload a finding with JSON details."""
    object_id = uuid4()
    finding = Finding(
        kind="prefix_multiple_sites",
        severity="warning",
        message="Prefix belongs to multiple sites.",
        object_type="network_prefix",
        object_id=object_id,
        details={
            "prefix": "10.131.0.0/22",
            "site_count": 2,
            "sites": ["DE-MAN-01", "DE-MAN-02"],
        },
    )
    finding_id = finding.id

    with session_factory() as session:
        session.add(finding)
        session.commit()

    with session_factory() as session:
        loaded = session.get(Finding, finding_id)

        assert loaded is not None
        assert loaded.id == finding_id
        assert loaded.kind == "prefix_multiple_sites"
        assert loaded.severity == "warning"
        assert loaded.message == "Prefix belongs to multiple sites."
        assert loaded.object_type == "network_prefix"
        assert loaded.object_id == object_id
        assert loaded.details == {
            "prefix": "10.131.0.0/22",
            "site_count": 2,
            "sites": ["DE-MAN-01", "DE-MAN-02"],
        }


def test_finding_without_object_reference(
    session_factory: sessionmaker[Session],
) -> None:
    """Persist findings without domain-object references."""
    finding = Finding(
        kind="collection_incomplete",
        severity="info",
        message="Some collection sources were unavailable.",
    )
    finding_id = finding.id

    with session_factory() as session:
        session.add(finding)
        session.commit()

    with session_factory() as session:
        loaded = session.get(Finding, finding_id)

        assert loaded is not None
        assert loaded.object_id is None
        assert loaded.object_type is None
        assert loaded.details == {}


def test_findings_can_be_queried_by_object(
    session_factory: sessionmaker[Session],
) -> None:
    """Retrieve findings using the associated object UUID."""
    object_id = uuid4()

    with session_factory() as session:
        session.add_all(
            [
                Finding(
                    "identity_conflict",
                    "error",
                    "Conflicting serial numbers.",
                    object_type="network_device",
                    object_id=object_id,
                ),
                Finding(
                    "missing_attribute",
                    "warning",
                    "Missing manufacturer.",
                    object_type="network_device",
                    object_id=object_id,
                ),
                Finding(
                    "unrelated",
                    "info",
                    "Different device.",
                    object_type="network_device",
                    object_id=uuid4(),
                ),
            ]
        )
        session.commit()

    with session_factory() as session:
        findings = session.scalars(
            select(Finding).where(Finding.object_id == object_id)
        ).all()

        assert len(findings) == 2
        assert {f.kind for f in findings} == {
            "identity_conflict",
            "missing_attribute",
        }


def test_findings_can_be_queried_by_kind(
    session_factory: sessionmaker[Session],
) -> None:
    """Filter findings by classification."""
    with session_factory() as session:
        session.add_all(
            [
                Finding("identity_conflict", "warning", "First conflict."),
                Finding("identity_conflict", "error", "Second conflict."),
                Finding("missing_attribute", "info", "Missing value."),
            ]
        )
        session.commit()

    with session_factory() as session:
        findings = session.scalars(
            select(Finding).where(
                Finding.kind == "identity_conflict"
            )
        ).all()

        assert len(findings) == 2


def test_duplicate_finding_identity_is_rejected(
    session_factory: sessionmaker[Session],
) -> None:
    """Reject duplicate finding primary keys."""
    identifier = uuid4()

    with session_factory() as session:
        session.add(
            Finding("first", "info", "Original finding.", id=identifier)
        )
        session.commit()

    with session_factory() as session:
        session.add(
            Finding("second", "warning", "Duplicate.", id=identifier)
        )

        with pytest.raises(IntegrityError):
            session.flush()

        session.rollback()


def test_uncommitted_finding_is_rolled_back(
    session_factory: sessionmaker[Session],
) -> None:
    """Discard findings when the transaction is not committed."""
    finding = Finding(
        "identity_conflict",
        "warning",
        "Potential identity conflict.",
    )
    finding_id = finding.id

    with session_factory() as session:
        session.add(finding)
        session.flush()

    with session_factory() as session:
        assert session.get(Finding, finding_id) is None
