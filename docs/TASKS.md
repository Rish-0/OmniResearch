# OmniResearch Task Plan

Execute tasks in order, one per session.

## T00 Bootstrap
- Monorepo skeleton per REPO LAYOUT (create only directories needed now); each Python package has its own pyproject.toml in one uv workspace; apps/web = Vite + React 18 + TypeScript strict with a placeholder page (pnpm).
- Makefile targets: up, down, test, lint, typecheck, migrate, schemas.
- infra/docker/compose.yml: postgres:16 (with a separate "mlflow" database), redis:7, qdrant, minio, mlflow on an internal network; .env.example.
- GitHub Actions CI: ruff, mypy --strict, pytest, import-linter, web lint+typecheck.
- import-linter contracts as in the dependency rule.
- **Accept**: `make up` brings all services healthy; `make lint typecheck test` pass; a test proves import-linter FAILS on a deliberately violating import; a CI check fails if any compose file mounts /var/run/docker.sock into an app service.

## T01 omni_contracts + omni_core
- omni_contracts (Pydantic v2): ResearchSpec, Plan, PlanTask, PlanDelta, FailureRecord + FailureClass enum (exact list above), AgentResult, ExperimentSpec (canonical_json() + spec_hash), DatasetSpec, AnalysisFacts, Claim, ClaimEvidence, Evidence, EvidencePack, GroundedAnswer, VerificationFinding, VerificationReport, BudgetConfig, WorkflowEvent.
- omni_core: pydantic-settings config, structured logging with context vars, UUIDv7 ids, error hierarchy (BudgetExceeded, GuardViolation...), Budget tracker, fingerprint(failure_class, error_signature, spec_hash) that normalises volatile tokens (paths, addresses, timestamps).
- `make schemas` exports JSON Schema for every contract.
- **Accept**: spec_hash stable under key reordering and changes on any field change; Plan validator rejects cycles, unknown task types, tasks without acceptance criteria, budgets above session limits; PlanDelta validator rejects no-op deltas and deltas without a failure_id; fingerprint deterministic; all contracts round-trip JSON. No I/O and no internal imports in these packages.

## T02 Database
- SQLAlchemy 2.0 async models for EVERY table listed in DATA, with real types, FKs, CHECK constraints (enums as TEXT + CHECK), org_id on tenant tables, timestamps.
- Alembic initial migration with sensible indexes (tasks(session_id,status); task_attempts(idempotency_key) unique; workflow_events(session_id,seq); claims(session_id,status); claim_evidence(claim_id); results(run_id,metric); failures(session_id,fingerprint); partial index on non-terminal research_sessions; trigram/FTS on papers.title) and monthly partitioning (or a documented stub) for workflow_events, audit_log, error_log, llm_calls.
- Repositories for sessions, tasks/attempts, events, claims, results, failures, memory_events.
- emit_event(txn, session_id, type, ...) allocating a gapless per-session seq inside the caller's transaction.
- DB role setup so the app role cannot UPDATE/DELETE audit_log.
- **Accept** (testcontainers Postgres): migration up/down works; duplicate idempotency_key rejected; concurrent emit_event calls yield strictly increasing gapless seq per session; app role UPDATE on audit_log denied; a seeded traceability query works: claim -> claim_evidence -> result -> run -> dataset_version.

## T03 LLM Gateway
(role routing, structured output with <=2 repair retries, fallback, circuit breaker, budget cap, redaction, FakeProvider + cassettes; verifier family != analyst/writer)

## T04 Agent Framework + Memory Service
(tool registry, allowlists, step ceilings, repeat-call detector + T1/T2/T3 memory, deterministic Research Brief)

## T05 Orchestrator
LangGraph state machine with fork/join, scheduler with stale-subtree invalidation, guards, PostgresSaver, lease/resume, Celery queues, stub agents.

## T06 API + SSE + JWT/RBAC + Audit

## T07 Ingestion Pipeline

## T08 RAG Service

## T09 Planner + Failure Triage + Literature Agent + Connectors

## T10 Dataset Agent + Staging Job

## T11 Sandbox Runner + omni_harness + Images

## T12 Experiment Service + Agent + MLflow

## T13 omni_analysis + Analysis Agent

## T14 Verification Agent V1-V6 + Replan Wiring

## T15 Writer + Report Lint + Export

## T16 Frontend MVP

## T17 Golden E2E Test + Red-Team Suite + Observability + Runbook

## Out of Scope (later phases)
Kubernetes/gVisor rollout, multi-tenant RLS, event-driven suspend/resume, PDF export, cross-project memory, equation-to-LaTeX, V7 reproducibility re-run.
