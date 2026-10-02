"""Unit tests for Pydantic v2 contract models in omni_contracts."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from omni_contracts.enums import (
    TaskType,
)
from omni_contracts.models import (
    BudgetConfig,
    DatasetRef,
    ExperimentSpec,
    ModelSpec,
    Plan,
    PlanDelta,
    PlanTask,
    ResearchSpec,
)
from omni_core.ids import uuid7


def test_research_spec_validation() -> None:
    """ResearchSpec requires valid objective length."""
    spec = ResearchSpec(objective="Compare Transformer and traditional ML models")
    assert spec.objective.startswith("Compare Transformer")

    with pytest.raises(ValidationError):
        ResearchSpec(objective="short")


def test_experiment_spec_hash_stability() -> None:
    """spec_hash must be stable under field reordering and change on value modification."""
    session_id = uuid7()
    spec1 = ExperimentSpec(
        spec_id=uuid7(),
        session_id=session_id,
        task_id="exp_01",
        objective="Compare BERT vs SVM",
        dataset=DatasetRef(dataset_id=uuid7(), version_hash="hash_123"),
        models=[
            ModelSpec(name="svm", model_type="sklearn.svm.SVC", hyperparameters={"C": 1.0}),
            ModelSpec(name="bert", model_type="transformers.BertForSequenceClassification"),
        ],
        metrics=["accuracy", "f1"],
    )

    h1 = spec1.spec_hash
    assert len(h1) == 64, "SHA-256 hex digest length"
    assert spec1.spec_hash == h1, "Hash is deterministic"

    # Modify hyperparameter value -> spec_hash must change
    spec2 = ExperimentSpec(
        spec_id=spec1.spec_id,
        session_id=session_id,
        task_id="exp_01",
        objective="Compare BERT vs SVM",
        dataset=DatasetRef(dataset_id=spec1.dataset.dataset_id, version_hash="hash_123"),
        models=[
            ModelSpec(name="svm", model_type="sklearn.svm.SVC", hyperparameters={"C": 2.0}),
            ModelSpec(name="bert", model_type="transformers.BertForSequenceClassification"),
        ],
        metrics=["accuracy", "f1"],
    )

    assert spec2.spec_hash != h1, "Hash must change when hyperparameters change"


def test_plan_dag_cycle_detection() -> None:
    """Plan validator must reject cycles in the task DAG."""
    session_id = uuid7()
    task1 = PlanTask(
        task_id="t1",
        task_type=TaskType.LITERATURE_REVIEW,
        description="Search papers",
        depends_on=["t2"],  # Cycle: t1 -> t2 -> t1
        acceptance_criteria=["Found 5 papers"],
    )
    task2 = PlanTask(
        task_id="t2",
        task_type=TaskType.DATASET_DISCOVERY,
        description="Fetch SST-2",
        depends_on=["t1"],
        acceptance_criteria=["Downloaded SST-2"],
    )

    with pytest.raises(ValidationError, match="Plan DAG contains a cycle"):
        Plan(
            plan_id=uuid7(),
            session_id=session_id,
            version=1,
            tasks=[task1, task2],
            created_at=datetime.now(UTC),
        )


def test_plan_unknown_dependency_rejection() -> None:
    """Plan validator must reject dependencies on non-existent task IDs."""
    task = PlanTask(
        task_id="t1",
        task_type=TaskType.LITERATURE_REVIEW,
        description="Search papers",
        depends_on=["unknown_task"],
        acceptance_criteria=["Found papers"],
    )

    with pytest.raises(ValidationError, match="depends on unknown task"):
        Plan(
            plan_id=uuid7(),
            session_id=uuid7(),
            version=1,
            tasks=[task],
            created_at=datetime.now(UTC),
        )


def test_plan_cost_budget_check() -> None:
    """Plan validator rejects total estimated task cost exceeding session budget."""
    task = PlanTask(
        task_id="t1",
        task_type=TaskType.LITERATURE_REVIEW,
        description="Search papers",
        acceptance_criteria=["Found papers"],
        estimated_cost_usd=100.0,
    )

    budget = BudgetConfig(max_llm_cost_usd=50.0)

    with pytest.raises(ValidationError, match="exceeds session budget"):
        Plan(
            plan_id=uuid7(),
            session_id=uuid7(),
            version=1,
            tasks=[task],
            budget=budget,
            created_at=datetime.now(UTC),
        )


def test_plan_delta_no_op_rejection() -> None:
    """PlanDelta validator rejects deltas with no changes."""
    with pytest.raises(ValidationError, match="must make at least one change"):
        PlanDelta(
            delta_id=uuid7(),
            plan_id=uuid7(),
            session_id=uuid7(),
            failure_id=uuid7(),
            rationale="Did nothing",
        )


def test_contracts_json_roundtrip() -> None:
    """All contract models must serialize to JSON and deserialize back losslessly."""
    task = PlanTask(
        task_id="t1",
        task_type=TaskType.EXPERIMENT_EXECUTION,
        description="Run benchmark experiments",
        acceptance_criteria=["Accuracy > 80%"],
    )
    plan = Plan(
        plan_id=uuid7(),
        session_id=uuid7(),
        version=1,
        tasks=[task],
        created_at=datetime.now(UTC),
    )

    json_str = plan.model_dump_json()
    reconstructed = Plan.model_validate_json(json_str)

    assert reconstructed.plan_id == plan.plan_id
    assert reconstructed.tasks[0].task_id == "t1"
    assert reconstructed.tasks[0].task_type == TaskType.EXPERIMENT_EXECUTION
