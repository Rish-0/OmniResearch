"""Pydantic v2 contract models for OmniResearch agent communication."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from omni_contracts.enums import (
    ClaimStatus,
    FailureClass,
    MemoryEventType,
    TaskStatus,
    TaskType,
    VerificationVerdict,
    WorkflowEventType,
)

# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------


class ContractModel(BaseModel):
    """Base for all contract models with shared config."""

    model_config = ConfigDict(
        frozen=True,
        use_enum_values=False,
        populate_by_name=True,
        ser_json_timedelta="float",
    )


# ---------------------------------------------------------------------------
# Research spec & planning
# ---------------------------------------------------------------------------


class ResearchSpec(ContractModel):
    """High-level research objective from the user."""

    objective: str = Field(..., min_length=10, max_length=2000)
    constraints: list[str] = Field(default_factory=list)
    focus_areas: list[str] = Field(default_factory=list)
    exclude_areas: list[str] = Field(default_factory=list)


class BudgetConfig(ContractModel):
    """Resource budgets for a research session."""

    max_replans: int = Field(default=3, ge=0, le=10)
    max_task_attempts: int = Field(default=3, ge=1, le=10)
    max_llm_cost_usd: float = Field(default=50.0, gt=0)
    max_total_tokens: int = Field(default=2_000_000, gt=0)
    max_gpu_hours: float = Field(default=10.0, ge=0)
    max_wall_clock_seconds: int = Field(default=86400, gt=0)
    max_agent_steps: int = Field(default=100, ge=1)


class PlanTask(ContractModel):
    """A single task in the research plan DAG."""

    task_id: str = Field(..., pattern=r"^[a-z0-9_]+$")
    task_type: TaskType
    description: str = Field(..., min_length=5)
    depends_on: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(..., min_length=1)
    retry_budget: int = Field(default=3, ge=0, le=10)
    estimated_cost_usd: float = Field(default=0.0, ge=0)


class Plan(ContractModel):
    """A versioned research plan — a DAG of PlanTasks."""

    plan_id: UUID
    session_id: UUID
    version: int = Field(..., ge=1)
    tasks: list[PlanTask] = Field(..., min_length=1)
    budget: BudgetConfig = Field(default_factory=BudgetConfig)
    created_at: datetime

    @model_validator(mode="after")
    def validate_plan(self) -> Plan:
        """Validate the plan DAG: no cycles, valid types, acceptance criteria, budgets."""
        task_ids = {t.task_id for t in self.tasks}

        # Check all depends_on references exist
        for task in self.tasks:
            for dep in task.depends_on:
                if dep not in task_ids:
                    msg = f"Task '{task.task_id}' depends on unknown task '{dep}'"
                    raise ValueError(msg)

        # Cycle detection via topological sort (Kahn's algorithm)
        in_degree: dict[str, int] = {t.task_id: 0 for t in self.tasks}
        adjacency: dict[str, list[str]] = {t.task_id: [] for t in self.tasks}
        for task in self.tasks:
            for dep in task.depends_on:
                adjacency[dep].append(task.task_id)
                in_degree[task.task_id] += 1

        queue = [tid for tid, deg in in_degree.items() if deg == 0]
        visited = 0
        while queue:
            node = queue.pop(0)
            visited += 1
            for neighbor in adjacency[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if visited != len(self.tasks):
            msg = "Plan DAG contains a cycle"
            raise ValueError(msg)

        # Task-level budget cannot exceed session budget
        total_cost = sum(t.estimated_cost_usd for t in self.tasks)
        if total_cost > self.budget.max_llm_cost_usd:
            msg = (
                f"Total estimated task cost ({total_cost:.2f}) exceeds "
                f"session budget ({self.budget.max_llm_cost_usd:.2f})"
            )
            raise ValueError(msg)

        return self


class PlanDelta(ContractModel):
    """A delta to apply to an existing plan during replanning."""

    delta_id: UUID
    plan_id: UUID
    session_id: UUID
    failure_id: UUID
    tasks_to_add: list[PlanTask] = Field(default_factory=list)
    tasks_to_remove: list[str] = Field(default_factory=list)
    tasks_to_modify: dict[str, dict[str, Any]] = Field(default_factory=dict)
    rationale: str = Field(..., min_length=10)

    @model_validator(mode="after")
    def validate_delta(self) -> PlanDelta:
        """Reject no-op deltas and deltas without a failure_id."""
        if not self.tasks_to_add and not self.tasks_to_remove and not self.tasks_to_modify:
            msg = "PlanDelta must make at least one change"
            raise ValueError(msg)
        return self


# ---------------------------------------------------------------------------
# Failure tracking
# ---------------------------------------------------------------------------


class FailureRecord(ContractModel):
    """Structured failure record with classification and fingerprint."""

    failure_id: UUID
    session_id: UUID
    task_id: str
    attempt_no: int = Field(..., ge=1)
    failure_class: FailureClass
    error_message: str
    error_signature: str
    traceback: str = ""
    spec_hash: str = ""
    fingerprint: str = ""
    occurred_at: datetime


# ---------------------------------------------------------------------------
# Agent results
# ---------------------------------------------------------------------------


class AgentResult(ContractModel):
    """Generic agent output contract."""

    agent_name: str
    task_id: str
    session_id: UUID
    status: TaskStatus
    outputs: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    steps_taken: int = Field(default=0, ge=0)
    tokens_used: int = Field(default=0, ge=0)
    cost_usd: float = Field(default=0.0, ge=0)
    duration_seconds: float = Field(default=0.0, ge=0)


# ---------------------------------------------------------------------------
# Experiment
# ---------------------------------------------------------------------------


class DatasetRef(ContractModel):
    """Reference to a specific dataset version."""

    dataset_id: UUID
    version_hash: str
    eval_split: str = "validation"


class ModelSpec(ContractModel):
    """Specification for a model to run in an experiment."""

    name: str
    model_type: str
    hyperparameters: dict[str, Any] = Field(default_factory=dict)


class ReplicationTarget(ContractModel):
    """Published results to replicate/compare against."""

    paper_id: UUID
    model_name: str
    metric_name: str
    reported_value: float
    tolerance: float = Field(default=0.02, ge=0)


class ExperimentSpec(ContractModel):
    """Full experiment specification. canonical_json() + spec_hash ensure reproducibility."""

    spec_id: UUID
    session_id: UUID
    task_id: str
    objective: str
    dataset: DatasetRef
    models: list[ModelSpec] = Field(..., min_length=1)
    metrics: list[str] = Field(..., min_length=1)
    seeds: list[int] = Field(default_factory=lambda: [42, 123, 456, 789, 1024])
    replication_targets: list[ReplicationTarget] = Field(default_factory=list)
    compute_profile: str = "cpu"
    timeout_seconds: int = Field(default=3600, gt=0)
    image_digest: str = ""
    harness_version: str = "0.1.0"

    def canonical_json(self) -> str:
        """Produce a canonical JSON string with sorted keys for hashing."""
        data = self.model_dump(mode="json")
        return json.dumps(data, sort_keys=True, separators=(",", ":"))

    @property
    def spec_hash(self) -> str:
        """SHA-256 of the canonical JSON representation."""
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------


class DatasetSpec(ContractModel):
    """Dataset specification after evaluation by the Dataset Agent."""

    dataset_id: UUID
    name: str
    source: str
    version_hash: str
    task_fit_score: float = Field(..., ge=0.0, le=1.0)
    label_quality_score: float = Field(..., ge=0.0, le=1.0)
    size_samples: int = Field(..., gt=0)
    license: str = ""
    splits: list[str] = Field(default_factory=lambda: ["train", "validation", "test"])
    leakage_checked: bool = False
    staging_path: str = ""


# ---------------------------------------------------------------------------
# Analysis & Claims
# ---------------------------------------------------------------------------


class NumericBinding(ContractModel):
    """A specific number bound to a variable name in a claim."""

    variable: str
    value: float
    unit: str = ""
    source: str = ""  # e.g. "run_id:xxx metric:accuracy seed_agg:mean"


class AnalysisFacts(ContractModel):
    """Structured facts from the Analysis Agent."""

    session_id: UUID
    task_id: str
    summary: str
    numeric_bindings: list[NumericBinding] = Field(default_factory=list)
    statistical_tests: list[dict[str, Any]] = Field(default_factory=list)
    comparison_notes: list[str] = Field(default_factory=list)


class Evidence(ContractModel):
    """A single piece of evidence supporting or refuting a claim."""

    evidence_id: UUID
    evidence_type: str  # "experiment_result", "citation", "statistical_test"
    source_id: UUID  # ID of the source (run_id, paper_id, etc.)
    content: str
    quote: str = ""
    page: int | None = None
    bbox: list[float] | None = None  # [x0, y0, x1, y1]


class EvidencePack(ContractModel):
    """Collection of evidence items for grounded answers."""

    items: list[Evidence] = Field(default_factory=list)
    query: str = ""
    retrieval_scores: dict[str, float] = Field(default_factory=dict)


class GroundedAnswer(ContractModel):
    """An answer grounded in evidence with traceable citations."""

    answer: str
    evidence_ids: list[UUID] = Field(default_factory=list)
    quotes: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class ClaimEvidence(ContractModel):
    """Link between a claim and its supporting evidence."""

    claim_id: UUID
    evidence_id: UUID
    relationship: str = "supports"  # "supports", "contradicts", "qualifies"


class Claim(ContractModel):
    """A single research claim with numeric bindings and evidence links."""

    claim_id: UUID
    session_id: UUID
    text: str = Field(..., min_length=10)
    status: ClaimStatus = ClaimStatus.PENDING
    numeric_bindings: list[NumericBinding] = Field(default_factory=list)
    evidence_ids: list[UUID] = Field(default_factory=list)
    section: str = ""  # Which report section this belongs to


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


class VerificationFinding(ContractModel):
    """A single verification check result."""

    finding_id: UUID
    check_type: str  # V1..V7
    target_id: UUID  # What was checked
    verdict: VerificationVerdict
    details: str
    is_blocking: bool = True


class VerificationReport(ContractModel):
    """Aggregate verification results for a session."""

    report_id: UUID
    session_id: UUID
    findings: list[VerificationFinding] = Field(default_factory=list)
    overall_pass: bool = False
    created_at: datetime

    @model_validator(mode="after")
    def compute_overall(self) -> VerificationReport:
        """Overall PASS only if no blocking findings have non-SUPPORTED verdict."""
        blocking_failures = [
            f
            for f in self.findings
            if f.is_blocking and f.verdict != VerificationVerdict.SUPPORTED
        ]
        # Use object.__setattr__ since model is frozen
        object.__setattr__(self, "overall_pass", len(blocking_failures) == 0)
        return self


# ---------------------------------------------------------------------------
# Workflow events
# ---------------------------------------------------------------------------


class WorkflowEvent(ContractModel):
    """Outbox event for the workflow event stream."""

    event_id: UUID
    session_id: UUID
    seq: int = Field(..., ge=0)
    event_type: WorkflowEventType
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


# ---------------------------------------------------------------------------
# Memory events
# ---------------------------------------------------------------------------


class MemoryEvent(ContractModel):
    """Episodic memory ledger entry."""

    event_id: UUID
    session_id: UUID
    event_type: MemoryEventType
    agent: str
    task_id: str = ""
    content: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
