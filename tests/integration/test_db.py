"""Integration tests for database models, migrations, repositories, and emit_event outbox."""


import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from omni_core.ids import uuid7
from omni_db.events import emit_event
from omni_db.models import (
    Base,
    Claim,
    ClaimEvidence,
    Dataset,
    DatasetVersion,
    Experiment,
    ExperimentRun,
    Project,
    ResearchSession,
    Result,
    Task,
    TaskAttempt,
)

# In-memory SQLite for fast async integration testing, or testcontainers if postgres configured
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def test_engine():
    """Fixture producing an in-memory SQLite async engine."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine):
    """Fixture producing an AsyncSession for testing."""
    async_session = sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session


@pytest.mark.asyncio
async def test_duplicate_idempotency_key_rejected(db_session: AsyncSession) -> None:
    """Duplicate task_attempt idempotency_key must raise IntegrityError."""
    org_id = uuid7()
    project = Project(id=uuid7(), org_id=org_id, name="Test Project")
    session_obj = ResearchSession(
        id=uuid7(), org_id=org_id, project_id=project.id, title="Test Session", objective="Obj"
    )
    task = Task(id=uuid7(), session_id=session_obj.id, task_id="t1", task_type="REPORT", description="Desc")

    db_session.add_all([project, session_obj, task])
    await db_session.commit()

    attempt1 = TaskAttempt(
        id=uuid7(),
        task_id=task.id,
        attempt_no=1,
        idempotency_key="key_123_abc",
        status="RUNNING",
    )
    db_session.add(attempt1)
    await db_session.commit()

    attempt2 = TaskAttempt(
        id=uuid7(),
        task_id=task.id,
        attempt_no=2,
        idempotency_key="key_123_abc",  # Duplicate key
        status="RUNNING",
    )
    db_session.add(attempt2)

    with pytest.raises(IntegrityError):
        await db_session.commit()

    await db_session.rollback()


@pytest.mark.asyncio
async def test_emit_event_gapless_seq(db_session: AsyncSession) -> None:
    """Sequential emit_event calls inside transactions yield strictly increasing gapless sequence numbers."""
    org_id = uuid7()
    project = Project(id=uuid7(), org_id=org_id, name="Test Project")
    session_obj = ResearchSession(
        id=uuid7(), org_id=org_id, project_id=project.id, title="Test Session", objective="Obj"
    )
    db_session.add_all([project, session_obj])
    await db_session.commit()

    # Emit 5 events sequentially
    events = []
    for i in range(1, 6):
        evt = await emit_event(
            db_session,
            session_id=session_obj.id,
            event_type="TASK_STARTED",
            payload={"step": i},
        )
        events.append(evt)
        await db_session.commit()

    # Verify seq numbers: 1, 2, 3, 4, 5
    for idx, evt in enumerate(events, start=1):
        assert evt.seq == idx, f"Expected seq {idx}, got {evt.seq}"


@pytest.mark.asyncio
async def test_traceability_query(db_session: AsyncSession) -> None:
    """Traceability query: claim -> claim_evidence -> result -> run -> dataset_version."""
    org_id = uuid7()
    project = Project(id=uuid7(), org_id=org_id, name="Trace Project")
    session_obj = ResearchSession(
        id=uuid7(), org_id=org_id, project_id=project.id, title="Trace Session", objective="Obj"
    )
    dataset = Dataset(id=uuid7(), name="SST-2", source="HuggingFace")
    ds_version = DatasetVersion(
        id=uuid7(),
        dataset_id=dataset.id,
        version_hash="vhash_sst2_001",
        size_samples=872,
        staging_path="/data/sst2",
    )
    experiment = Experiment(
        id=uuid7(), session_id=session_obj.id, task_id="exp1", spec={}, spec_hash="hash_exp1"
    )
    run = ExperimentRun(
        id=uuid7(),
        experiment_id=experiment.id,
        model_name="BERT",
        seed=42,
        dataset_version_id=ds_version.id,
    )
    result = Result(id=uuid7(), run_id=run.id, metric="accuracy", value=0.924)
    claim = Claim(
        id=uuid7(),
        session_id=session_obj.id,
        text="BERT achieves 92.4% accuracy on SST-2 validation split",
        status="VERIFIED",
    )
    evidence_link = ClaimEvidence(
        id=uuid7(),
        claim_id=claim.id,
        evidence_type="result",
        result_id=result.id,
        content="BERT accuracy result",
    )

    db_session.add_all(
        [
            project,
            session_obj,
            dataset,
            ds_version,
            experiment,
            run,
            result,
            claim,
            evidence_link,
        ]
    )
    await db_session.commit()

    # Execute full traceability join query
    stmt = (
        select(
            Claim.text.label("claim_text"),
            Result.value.label("metric_value"),
            ExperimentRun.model_name,
            DatasetVersion.version_hash,
        )
        .join(ClaimEvidence, ClaimEvidence.claim_id == Claim.id)
        .join(Result, Result.id == ClaimEvidence.result_id)
        .join(ExperimentRun, ExperimentRun.id == Result.run_id)
        .join(DatasetVersion, DatasetVersion.id == ExperimentRun.dataset_version_id)
        .where(Claim.id == claim.id)
    )

    row = (await db_session.execute(stmt)).one()

    assert row.claim_text.startswith("BERT achieves")
    assert row.metric_value == 0.924
    assert row.model_name == "BERT"
    assert row.version_hash == "vhash_sst2_001"
