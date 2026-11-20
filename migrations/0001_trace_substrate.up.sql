-- StellarWeave trace substrate — PR1
-- runs / steps / tool_calls. Hot index only; full payloads live in
-- immutable object storage (PayloadRef columns are JSONB pointers).
-- Postgres 16. Partitioning: steps/runs by month on created_at (PR2
-- introduces the partitioned parent tables; PR1 keeps plain tables so
-- the migration itself stays trivially reversible).

BEGIN;

CREATE TABLE IF NOT EXISTS runs (
    run_id        TEXT PRIMARY KEY,
    task_id       TEXT NOT NULL,
    tenant_id     TEXT NOT NULL,
    status        TEXT NOT NULL CHECK (status IN ('running','succeeded','failed','aborted')),
    dag_spec_ref  JSONB NOT NULL,
    judge_scores  JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at   TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_runs_tenant_created ON runs (tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_runs_task ON runs (task_id);

CREATE TABLE IF NOT EXISTS steps (
    step_id        TEXT PRIMARY KEY,
    run_id         TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    step_index     INTEGER NOT NULL CHECK (step_index >= 0),
    agent_role     TEXT NOT NULL CHECK (agent_role IN ('planner','acquisition','support','content','analytics','judge')),
    prompt_version TEXT NOT NULL,
    model          TEXT NOT NULL,
    input_ref      JSONB NOT NULL,
    output_ref     JSONB,
    tokens         JSONB NOT NULL,
    latency_ms     INTEGER NOT NULL CHECK (latency_ms >= 0),
    ttft_ms        INTEGER NOT NULL CHECK (ttft_ms >= 0 AND ttft_ms <= latency_ms),
    parent_step_id TEXT REFERENCES steps(step_id),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (run_id, step_index)
);
CREATE INDEX IF NOT EXISTS idx_steps_run ON steps (run_id, step_index);
CREATE INDEX IF NOT EXISTS idx_steps_role_prompt ON steps (agent_role, prompt_version);

CREATE TABLE IF NOT EXISTS tool_calls (
    tool_call_id  TEXT PRIMARY KEY,
    step_id       TEXT NOT NULL REFERENCES steps(step_id) ON DELETE CASCADE,
    tool_name     TEXT NOT NULL,
    arguments_ref JSONB NOT NULL,
    result_ref    JSONB,
    status        TEXT NOT NULL CHECK (status IN ('ok','error','timeout','rejected')),
    latency_ms    INTEGER NOT NULL CHECK (latency_ms >= 0),
    error         TEXT
);
CREATE INDEX IF NOT EXISTS idx_tool_calls_step ON tool_calls (step_id);

COMMIT;