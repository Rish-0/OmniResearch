"""Export JSON schemas for all contract models to the schemas/ directory."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from omni_contracts.models import (
    AgentResult,
    AnalysisFacts,
    BudgetConfig,
    Claim,
    ClaimEvidence,
    DatasetSpec,
    Evidence,
    EvidencePack,
    ExperimentSpec,
    FailureRecord,
    GroundedAnswer,
    MemoryEvent,
    Plan,
    PlanDelta,
    PlanTask,
    ResearchSpec,
    VerificationFinding,
    VerificationReport,
    WorkflowEvent,
)

if TYPE_CHECKING:
    from pydantic import BaseModel

MODELS: list[type[BaseModel]] = [
    ResearchSpec,
    BudgetConfig,
    PlanTask,
    Plan,
    PlanDelta,
    FailureRecord,
    AgentResult,
    ExperimentSpec,
    DatasetSpec,
    AnalysisFacts,
    Claim,
    ClaimEvidence,
    Evidence,
    EvidencePack,
    GroundedAnswer,
    VerificationFinding,
    VerificationReport,
    WorkflowEvent,
    MemoryEvent,
]


def main() -> None:
    """Export JSON Schema for every contract model."""
    out_dir = Path("schemas")
    out_dir.mkdir(exist_ok=True)

    for model_cls in MODELS:
        schema = model_cls.model_json_schema()
        path = out_dir / f"{model_cls.__name__}.json"
        path.write_text(json.dumps(schema, indent=2) + "\n")
        print(f"  Exported {path}")  # noqa: T201

    print(f"\nExported {len(MODELS)} schemas to {out_dir}/")  # noqa: T201


if __name__ == "__main__":
    main()
