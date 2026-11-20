# StellarWeave Trace

Evaluation infrastructure for multi-agent business automation — trace substrate + three-layer assertion funnel. **Built with Devin.**

The thesis: nine out of ten multi-agent founders die on eval infrastructure and multi-turn latency. This repo is the spine that keeps the tenth alive — one trace layer feeds both evaluation (counterfactual replay for credit assignment) and latency analysis (DAG critical-path budgets), built once.

## Architecture

```
runs ──< steps ──< tool_calls        (Postgres hot index)
  │        │
  └────────┴── PayloadRef ──► immutable object storage (byte-exact inputs/outputs)
```

- **Pydantic is the single schema source.** DDL columns and the assertion-layer JSON Schema (`schemas/`) are both derived from `src/stellarweave_trace/schema.py`; a model change without a migration fails CI.
- **Scores are `(score, judge_version, rubric_version)` triples.** Judge upgrades shift every historical score silently — cross-version comparison is forbidden at the reporting layer.
- **`prompt_version` per step.** Counterfactual replay (PR6) bisects a failed run to a specific `(agent_role, prompt_version)` pair by replaying downstream steps with golden upstream outputs.
- **DAG, not chain.** `steps.parent_step_id` is a DAG edge; latency budgets are enforced on `ttft_ms` along the critical path.
- **Boring tech on purpose:** Python 3.12+, Pydantic v2, Postgres 16, S3-compatible storage. No Redis until a measured bottleneck demands it — every extra component is one more way to die.

## Roadmap (6 PRs, ~140 ACU)

| PR | Scope | Acceptance |
|----|-------|------------|
| **1 (this)** | schema + reversible migration | migrations reversible; schema unit tests green |
| 2 | ingestion worker (FastAPI + PG `SKIP LOCKED`) | 1k traces/s, zero loss, p99 write < 50ms |
| 3 | payload tiering (PG index / immutable S3) | byte-exact replay of any historical trace |
| 4 | assertion DSL (deterministic layer) | < 1% false-kill on 500 replayed traces |
| 5 | CI funnel (150-case PR smoke / 2000 nightly) | smoke < 8 min; nightly report auto-generated |
| 6 | judge calibration + counterfactual replay | Cohen's κ ≥ 0.7 vs 200 golden labels; injected bad prompt located in ≤ 3 bisections |

## Dev

```bash
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
python -m stellarweave_trace.schema_export   # refresh schemas/
pytest -q                                     # schema + contract + property tests
```

Migration: `psql -f migrations/0001_trace_substrate.up.sql` · rollback: `...down.sql`.

## License

Apache-2.0.