
"""Test SQL finding repositories and Unit of Work transactions."""

from collections.abc import Iterator
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from netvoyager_database.exceptions import (
    RepositoryConflictError,
    TransactionError,
)
from netvoyager_database.repositories.findings import (
    SqlFindingRepository,
)
from netvoyager_database.unit_of_work.network_inventory import (
    NetworkInventoryUnitOfWork,
)
from netvoyager_intelligence.base import IntelligenceBase
from netvoyager_intelligence.evidence import EvidenceRecord
from netvoyager_intelligence.findings import Finding


@pytest.fixture
def session_factory() -> Iterator[sessionmaker[Session]]:
    """Provide an isolated intelligence database for repository tests."""
    engine = create_engine("sqlite+pysqlite:///:memory:")

    IntelligenceBase.metadata.create_all(engine)

    yield sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )

    engine.dispose()


def test_add_and_get_finding(
    session_factory: sessionmaker[Session],
) -> None:
    """Persist and retrieve a finding through the repository."""
    finding = Finding(
        kind="identity_conflict",
        severity="warning",
        message="Conflicting device attributes.",
    )
    finding_id = finding.id

    with NetworkInventoryUnitOfWork(session_factory) as uow:
        uow.findings.add(finding)
        uow.commit()

    with NetworkInventoryUnitOfWork(session_factory) as uow:
        loaded = uow.findings.get(finding_id)

        assert loaded is not None
        assert loaded.kind == "identity_conflict"
        assert loaded.severity == "warning"


def test_missing_finding_returns_none(
    session_factory: sessionmaker[Session],
) -> None:
    """Return None for an unknown finding identity."""
    with NetworkInventoryUnitOfWork(session_factory) as uow:
        assert uow.findings.get(uuid4()) is None


def test_findings_for_object(
    session_factory: sessionmaker[Session],
) -> None:
    """Retrieve findings by UUID with an optional type safeguard."""
    object_id = uuid4()

    first = Finding(
        kind="identity_conflict",
        severity="warning",
        message="First issue.",
        object_type="network_device",
        object_id=object_id,
    )
    second = Finding(
        kind="missing_attribute",
        severity="info",
        message="Second issue.",
        object_type="network_device",
        object_id=object_id,
    )
    unrelated = Finding(
        kind="other",
        severity="info",
        message="Other object type.",
        object_type="network_scope",
        object_id=object_id,
    )

    with NetworkInventoryUnitOfWork(session_factory) as uow:
        uow.findings.add(first)
        uow.findings.add(second)
        uow.findings.add(unrelated)
        uow.commit()

    with NetworkInventoryUnitOfWork(session_factory) as uow:
        all_results = uow.findings.for_object(object_id)
        filtered = uow.findings.for_object(
            object_id,
            object_type="network_device",
        )

        assert len(all_results) == 3
        assert {item.id for item in filtered} == {
            first.id,
            second.id,
        }


def test_findings_by_kind(
    session_factory: sessionmaker[Session],
) -> None:
    """Return only findings matching the requested classification."""
    with NetworkInventoryUnitOfWork(session_factory) as uow:
        uow.findings.add(
            Finding("identity_conflict", "warning", "First conflict.")
        )
        uow.findings.add(
            Finding("identity_conflict", "error", "Second conflict.")
        )
        uow.findings.add(
            Finding("missing_attribute", "info", "Missing value.")
        )
        uow.commit()

    with NetworkInventoryUnitOfWork(session_factory) as uow:
        results = uow.findings.find_by_kind("identity_conflict")

        assert len(results) == 2
        assert all(
            item.kind == "identity_conflict"
            for item in results
        )


def test_duplicate_finding_raises_repository_conflict(
    session_factory: sessionmaker[Session],
) -> None:
    """Translate duplicate primary keys to the Core-based exception."""
    identifier = uuid4()

    with NetworkInventoryUnitOfWork(session_factory) as uow:
        uow.findings.add(
            Finding("first", "info", "Original.", id=identifier)
        )
        uow.commit()

    with pytest.raises(RepositoryConflictError) as error:
        with NetworkInventoryUnitOfWork(session_factory) as uow:
            uow.findings.add(
                Finding(
                    "second",
                    "warning",
                    "Duplicate.",
                    id=identifier,
                )
            )

    assert error.value.code == "storage.finding_conflict"


def test_uncommitted_finding_is_rolled_back(
    session_factory: sessionmaker[Session],
) -> None:
    """Discard findings when the Unit of Work exits without commit."""
    finding = Finding(
        "identity_conflict",
        "warning",
        "Uncommitted finding.",
    )
    finding_id = finding.id

    with NetworkInventoryUnitOfWork(session_factory) as uow:
        uow.findings.add(finding)

    with NetworkInventoryUnitOfWork(session_factory) as uow:
        assert uow.findings.get(finding_id) is None


def test_evidence_and_finding_commit_together(
    session_factory: sessionmaker[Session],
) -> None:
    """Persist evidence and findings within one transaction."""
    evidence = EvidenceRecord(
        source="excel",
        details={"row": 10},
    )
    finding = Finding(
        "missing_attribute",
        "warning",
        "Missing serial number.",
    )

    with NetworkInventoryUnitOfWork(session_factory) as uow:
        uow.evidence.add(evidence)
        uow.findings.add(finding)
        uow.commit()

    with NetworkInventoryUnitOfWork(session_factory) as uow:
        assert uow.evidence.get(evidence.id) is not None
        assert uow.findings.get(finding.id) is not None


def test_evidence_and_finding_roll_back_together(
    session_factory: sessionmaker[Session],
) -> None:
    """Roll back both repositories without an explicit commit."""
    evidence = EvidenceRecord(
        source="excel",
        details={"row": 11},
    )
    finding = Finding(
        "missing_attribute",
        "warning",
        "Missing model.",
    )

    with NetworkInventoryUnitOfWork(session_factory) as uow:
        uow.evidence.add(evidence)
        uow.findings.add(finding)

    with NetworkInventoryUnitOfWork(session_factory) as uow:
        assert uow.evidence.get(evidence.id) is None
        assert uow.findings.get(finding.id) is None


def test_findings_require_active_unit_of_work(
    session_factory: sessionmaker[Session],
) -> None:
    """Reject repository access outside an active transaction scope."""
    uow = NetworkInventoryUnitOfWork(session_factory)

    with pytest.raises(TransactionError):
        _ = uow.findings
