# OmniResearch Architecture

## 1. STATE MACHINE (session level)

INIT -> PLAN -> fork(RESEARCH || DATASET) -> join -> EXPERIMENT -> ANALYSIS -> VERIFY -> PASS: REPORT -> COMPLETE | FAIL: REPLAN -> re-enter at the earliest affected phase (RESEARCH/DATASET/EXPERIMENT/ANALYSIS), recomputing only the stale downstream task subtree. Extra states: PAUSED, NEEDS_HUMAN, FAILED, CANCELLED. Planner output is a versioned task DAG (types: LITERATURE_REVIEW, DATASET_DISCOVERY, METHODOLOGY_SELECTION, EXPERIMENT_DESIGN, EXPERIMENT_EXECUTION, RESULT_ANALYSIS, VERIFICATION, REPORT) with depends_on, acceptance criteria and retry budgets.

Retries on three levels: L1 call retry (backoff+jitter, circuit breaker); L2 agent-local retry (schema repair <=2, code fix <=3); L3 replan (max_replans default 3).

Loop prevention (in code): session budgets (replans, task attempts=3, LLM USD, tokens, GPU hours, wall clock); failure fingerprints reject repeats; replans must change spec hash/tool/dataset/protocol; monotonic-progress check; agent step ceilings and repeated-identical-tool-call detection; LangGraph recursion_limit only as a backstop; on exhaustion -> NEEDS_HUMAN or REPORT(PARTIAL) by policy; unverifiable claims may be weakened/dropped and listed under Limitations.

Checkpoints: LangGraph PostgresSaver after every node + domain checkpoints in Postgres; idempotency keys (session,task,attempt), (spec_hash,model,seed,attempt), (sha256,parser_version,stage); worker lease + heartbeat + resume.

## 2. AGENTS

Each agent = LangGraph subgraph: load_context -> (reason <-> tool_call)* -> validate_output -> persist -> emit_result; typed tools with per-agent allowlists.

- **Research Planner**: objective -> ResearchSpec -> Plan DAG; also "replan mode" producing a PlanDelta after deterministic Failure Triage. Tools: memory brief/recall, cheap literature preview, compute estimate. No code execution.
- **Literature Agent**: arXiv/OpenAlex/Semantic Scholar (domain allowlist, SSRF guard, source fallback), dedupe DOI->arXivID->fuzzy title, LLM screening with rationale, PDF fetch, ingestion dispatch, extraction of methods/datasets/settings/reported results via reader-mode.
- **Dataset Agent**: candidates (from ingested papers + hubs e.g. SST-2/IMDb/Amazon Reviews), rubric scoring in CODE (task fit, labels, size vs compute, license, prior usage, comparability), trusted staging job (download, checksum, immutable version hash, validation incl. leakage and split semantics) -> DatasetSpec -> Memory.
- **Experiment Agent**: design -> ExperimentSpec (JSON, spec_hash) -> code against trusted harness -> AST static checks -> smoke run (1% data) -> full runs -> diagnose -> bounded local repair -> results to Memory.
- **Analysis Agent**: deterministic stats first via trusted omni_analysis (seed aggregation, CIs, paired bootstrap, McNemar), then compare_findings (OUR_RUN vs PUBLISHED, comparability check), then LLM interpretation limited to AnalysisFacts, output = structured Claims with numeric_bindings and evidence links.
- **Verification Agent**: V1 experiment ran; V2 numbers match (recomputed within tolerance); V3 dataset version correct + no leakage; V4 citations resolve (chunk/table/figure exists, quote present, DOI valid); V5 LLM entailment judge (different model family than analyst/writer) returning SUPPORTED/PARTIAL/UNSUPPORTED/CONTRADICTED/ABSTAIN; V6 comparison validity; V7 reproducibility re-run (later phase). Binary PASS/FAIL; any blocking finding = FAIL; ABSTAIN/infra error = fail-closed.
- **Research Writer**: only VERIFIED claims, {{claim:ID}} markers, sections Abstract, Introduction, Literature Review, Methodology, Dataset, Experiments, Results, Discussion, Limitations, Conclusion, References; deterministic report lint; PARTIAL path.

**FailureClass enum and allowed repairs**: CODE_ERROR (regenerate with traceback), RESOURCE_ERROR (smaller batch/subset/bigger profile), MISSING_DEPENDENCY (alternative lib or human-approved image), DATA_ISSUE (re-validate/re-split/switch dataset), EVIDENCE_INSUFFICIENT (widen search), NUMBER_MISMATCH (recompute), UNSUPPORTED_CLAIM (rewrite/drop/add experiment e.g. more seeds or significance test), DISCREPANCY_WITH_PUBLISHED (investigate preprocessing/split/hyperparameters), INVALID_COMPARISON (align protocol or relabel non-comparable), TOOL_UNAVAILABLE (switch source/tool).

## 3. MULTIMODAL RAG

PDF -> triage (native vs scanned) -> layout parse (PyMuPDF with bbox, Unstructured hi_res for tables; behind a PdfParser interface because PyMuPDF is AGPL) -> section reconstruction + caption linking -> text chunks (hierarchical, ~300-500 tokens, ~10-15% overlap, never cross sections, prefix "title | section path"), tables (kept as ONE logical unit: cells_json + CSV + linearized-row rendering + summary; numeric rows extracted into reported_results table), figures (crop to object storage + caption + OCR PaddleOCR->Tesseract + VLM description) -> BGE-M3 dense+sparse embeddings (+content-hash cache) -> Qdrant collections paper_text, paper_tables, paper_figures (payload indexes: org_id, paper_id, section_type, page, etc.; deterministic point IDs). Retrieval: query analysis -> hybrid dense+sparse with RRF (Qdrant Query API) -> mandatory server-side filters -> cross-encoder rerank -> evidence pack E1..En with locators -> grounded LLM/VLM answer as JSON with evidence_ids/quotes -> deterministic validation (ids exist, quotes fuzzy-match) -> citations resolvable to (paper, page, bbox). Degraded modes: sparse-only, no rerank, explicit insufficient_evidence. Ingestion-time hidden-text/injection scanning sets injection_score.

## 4. MEMORY (three tiers)

T1 working state = LangGraph checkpoints (pointers). T2 episodic ledger in Postgres (plans, decisions, selected papers/datasets, experiments, runs, results, FAILURES with fingerprints, verifications, append-only memory_events, supersession not deletion) = source of truth for exact facts. T3 semantic memory = Qdrant research_memory (fuzzy recall, returns entity IDs resolved in T2). Each agent gets a deterministic "Research Brief" compiled from T2 (no LLM). Only the Memory Service writes, from validated contract objects, with provenance.

## 5. EXPERIMENT INFRASTRUCTURE

Control plane (Experiment Service, holds keys/DB) vs execution plane (Sandbox Runner + ephemeral containers holding nothing). ExperimentSpec: objective, dataset{id, version_hash, eval_split}, models[], metrics, seeds (3-5), replication_targets from published results, compute profile, timeout, image digest, harness version. Code generation: LLM writes only model-specific code (build_model/fit/predict) against trusted omni_harness which owns data loading, seeding, splits, metric computation FROM predictions.parquet, results serialization. Sandbox: non-root, cap-drop ALL, no-new-privileges, seccomp, read-only rootfs, tmpfs workspace, network none, mounts only /data (ro) and /out (rw), cpu/mem/pids limits, wall-clock timeout, ephemeral, no runtime pip installs (pinned images), gVisor in production. Datasets/weights are downloaded only by a separate trusted staging job. MLflow is logged post-hoc by a trusted collector (parent run per spec, child per model x seed; tags session_id, task_id, attempt_no, spec_hash, code_sha256, dataset_version_hash, image_digest); MLflow is never reachable from the sandbox. Reproducibility manifest: spec_hash, code sha256, image digest, pip freeze, dataset version hash, weights revision, seeds, hardware, determinism flags; reproduce(run_id).

## 6. DATA (Postgres, UUIDv7, org_id on tenant tables, JSONB for versioned schemas)

**Tables**: users, roles, project_members, projects, research_sessions (status, budgets, usage, replan_count, checkpoint_thread_id, lease), plan_versions, tasks, task_attempts (idempotency_key unique, fingerprint), papers, paper_assets (page/figure/table/equation), project_papers, ingestion_jobs, reported_results, datasets, dataset_versions, project_datasets, experiments (spec, spec_hash), experiment_runs, results, artifacts, analyses, claims, claim_evidence, citations, verifications, verification_findings, reports, report_sections, decisions, failures, memory_events, agent_runs, agent_tool_calls, llm_calls, workflow_events (outbox, PK(session_id, seq)), audit_log (append-only, hash-chained later), error_log, embedding_cache.

**Traceability**: report sentence -> claim -> claim_evidence -> (result -> run -> dataset_version) or (citation -> paper asset -> paper).

**Object storage**: omni-papers/{paper_id}/(original.pdf|parsed|figures|tables), omni-datasets/{dataset_id}/{version_hash}, omni-models, omni-experiments/{project}/{session}/{experiment}/{run}/(code|logs|out|plots|manifest.json), omni-reports/{report_id}/v{n}, omni-mlflow.

## 7. API / REALTIME / FRONTEND

FastAPI: JWT via OIDC-shaped interface, RBAC (viewer, researcher, project_admin, org_admin), Idempotency-Key on POSTs, RFC 7807 errors, rate limits, audit middleware. REST: /v1/projects; /v1/projects/{pid}/research-sessions (POST -> 202); /v1/research-sessions/{sid} (status), /pause /resume /cancel /approve /guidance, /plans, /tasks, /events (SSE + ?since_seq= replay), /papers, /datasets, /experiments, /runs/{rid}/logs (SSE), /results, /analysis, /claims, /verifications, /reports/latest and /reports/{rid}/export.

Use SSE (not WebSockets): transactional outbox row -> Redis Streams -> SSE with Last-Event-ID replay from Postgres, polling fallback if Redis is down.

Frontend pages: New Research, Session Dashboard (phase stepper, React Flow task DAG, live events, budget meters), Plan/Timeline, Literature (pdf.js with bbox highlight), Datasets matrix, Experiments (logs, MLflow link), Results (ours vs published), Verification (check matrix, claims with evidence popovers), Report (hoverable citations, export).

## 8. SECURITY

Prompt-injection defense = privilege separation (reader LLM calls have no tools), delimiting/spotlighting, ingestion scanning, per-agent tool allowlists, domain-allowlisted connectors + SSRF guard, strict JSON outputs, human approval for new dependencies / big compute. Secrets in a secret manager, redacted from logs/prompts, never in sandboxes. Audit log for auth/state-changing actions.

Retry/fallback matrix: LLM (secondary provider / smaller model), VLM (caption+OCR only), scholarly APIs (S2 <-> OpenAlex <-> arXiv), Qdrant (Postgres FTS), embedding/reranker (sparse-only/fused order).

## 9. REPO LAYOUT (monorepo)

```
apps/api, apps/web
packages/omni_core, omni_contracts, omni_db, omni_llm,
  omni_agents (framework, planner, literature, dataset, experiment, analysis, verification, writer, tools),
  omni_orchestration, omni_rag, omni_ingestion, omni_memory,
  omni_experiments, omni_harness (trusted, copied into sandbox images),
  omni_analysis (trusted), omni_observability
services/workers, sandbox_runner, embedding_service, scheduler
sandbox/images (cpu,gpu), policies, staging
infra/docker (compose), mlflow, k8s, terraform, observability
tests/unit, integration (testcontainers), contract, sandbox_security, redteam, evals, e2e, fixtures
Makefile, pyproject.toml (uv workspace), pnpm-workspace.yaml, .github/workflows
```

## 10. GOLDEN SCENARIO (for the final E2E test, T17)

Query: "Compare Transformer-based models with traditional ML models for sentiment classification."

Plan v1 -> literature + dataset (select SST-2; evaluation uses the validation split because benchmark test labels are hidden) -> experiment with SVM, Logistic Regression (TF-IDF), BERT; metrics Accuracy/Precision/Recall/F1; 5 seeds -> illustrative results (SVM 84.2/83.7, LogReg 85.1/84.6, BERT 92.4/91.8; published BERT F1 90.8) -> analysis emits claims incl. "BERT's advantage is statistically significant" with NO evidence yet -> Verification FAIL (UNSUPPORTED_CLAIM) -> replan: add paired-bootstrap test on stored predictions (only ANALYSIS is stale) -> re-verify PASS -> report with Limitations (single dataset, validation split, earlier OOM adjustment).
