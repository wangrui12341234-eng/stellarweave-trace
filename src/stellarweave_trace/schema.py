"""Canonical trace schema for StellarWeave evaluation infrastructure.

Pydantic models are the SINGLE source of schema truth: the Postgres DDL
column list and the assertion-layer JSON Schema are both derived from
these models (see `schema_export.py` and `migrations/`).

Three tables: runs / steps / tool_calls.
Design rules (locked day one):
  * full payloads live in immutable object storage keyed by run_id —
    these rows are the hot index only (counterfactual replay needs the
    byte-exact inputs, the index needs to find them fast);
  * scores are ALWAYS stored as (score, judge_version, rubric_version)
    triples — cross-version comparison is forbidden (judge drift);
  * prompt_version is recorded per step — credit assignment via
    counterfactual replay bisects to a (agent_role, prompt_version) pair.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex


class StrictModel(BaseModel):
    """No silent field drops: unknown keys are a schema violation, not noise."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class AgentRole(str, Enum):
    PLANNER = "planner"
    ACQUISITION = "acquisition"
    SUPPORT = "support"
    CONTENT = "content"
    ANALYTICS = "analytics"
    JUDGE = "judge"


class RunStatus(str, Enum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ABORTED = "aborted"


class ToolCallStatus(str, Enum):
    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"
    REJECTED = "rejected"  # assertion layer refused the call before dispatch


class PayloadRef(StrictModel):
    """Pointer into immutable object storage. Never inline large payloads."""

    bucket: str = Field(min_length=1)
    key: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)


class TokenUsage(StrictModel):
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cached_input_tokens: int = Field(ge=0, default=0)

    @field_validator("cached_input_tokens")
    @classmethod
    def _cached_le_input(cls, v: int, info: Any) -> int:
        # A cache can never return more than was asked for.
        if "input_tokens" in info.data and v > info.data["input_tokens"]:
            raise ValueError("cached_input_tokens exceeds input_tokens")
        return v


class ToolCall(StrictModel):
    """One tool invocation inside a step. tool_calls table row."""

    tool_call_id: str = Field(default_factory=_new_id)
    step_id: str
    tool_name: str = Field(min_length=1)
    arguments_ref: PayloadRef
    result_ref: PayloadRef | None = None
    status: ToolCallStatus
    latency_ms: int = Field(ge=0)
    error: str | None = None


class Step(StrictModel):
    """One agent invocation inside a run. steps table row.

    latency_ms is wall time; ttft_ms is time-to-first-token (the DAG
    critical-path budget is enforced against ttft, not wall time).
    """

    step_id: str = Field(default_factory=_new_id)
    run_id: str
    step_index: int = Field(ge=0)
    agent_role: AgentRole
    prompt_version: str = Field(min_length=1)
    model: str = Field(min_length=1)
    input_ref: PayloadRef
    output_ref: PayloadRef | None = None
    tokens: TokenUsage
    latency_ms: int = Field(ge=0)
    ttft_ms: int = Field(ge=0)
    parent_step_id: str | None = None  # DAG edge, not a chain
    created_at: datetime = Field(default_factory=_utcnow)

    @field_validator("ttft_ms")
    @classmethod
    def _ttft_le_latency(cls, v: int, info: Any) -> int:
        if "latency_ms" in info.data and v > info.data["latency_ms"]:
            raise ValueError("ttft_ms exceeds latency_ms")
        return v


class JudgeScore(StrictModel):
    """The anti-drift triple. Cross-version comparison is a schema error
    at the reporting layer, not a footnote in a dashboard."""

    score: float = Field(ge=0.0, le=1.0)
    judge_version: str = Field(min_length=1)
    rubric_version: str = Field(min_length=1)


class Run(StrictModel):
    """One end-to-end task execution. runs table row."""

    run_id: str = Field(default_factory=_new_id)
    task_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    status: RunStatus
    dag_spec_ref: PayloadRef  # planner output: a DAG, never a chain
    judge_scores: tuple[JudgeScore, ...] = ()
    created_at: datetime = Field(default_factory=_utcnow)
    finished_at: datetime | None = None


# --- derived DDL contract -------------------------------------------------
# Column names are derived from the models, so a model change that is not
# reflected in a migration fails CI (tests/test_schema_contract.py).

TABLE_MODELS: dict[str, type[StrictModel]] = {
    "runs": Run,
    "steps": Step,
    "tool_calls": ToolCall,
}


def table_columns(table: str) -> list[str]:
    return list(TABLE_MODELS[table].model_fields.keys())


JSONB_COLUMNS: dict[str, frozenset[str]] = {
    "runs": frozenset({"dag_spec_ref", "judge_scores"}),
    "steps": frozenset({"input_ref", "output_ref", "tokens"}),
    "tool_calls": frozenset({"arguments_ref", "result_ref"}),
}