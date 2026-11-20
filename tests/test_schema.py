"""Schema invariants — the deterministic assertion layer starts here."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from stellarweave_trace import JudgeScore, PayloadRef, Run, Step, TokenUsage, ToolCall


class TestPayloadRef:
    def test_valid(self, payload_ref):
        assert PayloadRef(**payload_ref).size_bytes == 1024

    @pytest.mark.parametrize("bad_sha", ["", "xyz", "a" * 63, "A" * 64])
    def test_sha256_must_be_64_lowercase_hex(self, payload_ref, bad_sha):
        with pytest.raises(ValidationError):
            PayloadRef(**{**payload_ref, "sha256": bad_sha})

    def test_negative_size_rejected(self, payload_ref):
        with pytest.raises(ValidationError):
            PayloadRef(**{**payload_ref, "size_bytes": -1})


class TestTokenUsage:
    def test_cached_cannot_exceed_input(self):
        with pytest.raises(ValidationError):
            TokenUsage(input_tokens=100, output_tokens=10, cached_input_tokens=101)

    def test_zero_cache_ok(self):
        t = TokenUsage(input_tokens=100, output_tokens=10)
        assert t.cached_input_tokens == 0


class TestStep:
    def test_valid(self, step_kwargs):
        s = Step(**step_kwargs)
        assert s.parent_step_id is None  # DAG root

    def test_ttft_cannot_exceed_latency(self, step_kwargs):
        with pytest.raises(ValidationError):
            Step(**{**step_kwargs, "ttft_ms": step_kwargs["latency_ms"] + 1})

    def test_unknown_role_rejected(self, step_kwargs):
        with pytest.raises(ValidationError):
            Step(**{**step_kwargs, "agent_role": "ceo"})

    def test_unknown_field_rejected(self, step_kwargs):
        # extra="forbid": a typo'd field must fail ingestion, not vanish.
        with pytest.raises(ValidationError):
            Step(**{**step_kwargs, "prompt_verison": "typo"})

    def test_negative_step_index_rejected(self, step_kwargs):
        with pytest.raises(ValidationError):
            Step(**{**step_kwargs, "step_index": -1})

    def test_frozen(self, step_kwargs):
        s = Step(**step_kwargs)
        with pytest.raises(ValidationError):
            s.latency_ms = 0


class TestJudgeScore:
    def test_triple_required(self):
        with pytest.raises(ValidationError):
            JudgeScore(score=0.9)  # missing judge_version + rubric_version

    @pytest.mark.parametrize("bad", [-0.01, 1.01])
    def test_score_bounds(self, bad):
        with pytest.raises(ValidationError):
            JudgeScore(score=bad, judge_version="j1", rubric_version="r1")


class TestRun:
    def test_scores_are_triples(self, payload_ref):
        run = Run(
            task_id="t1",
            tenant_id="acme",
            status="succeeded",
            dag_spec_ref=payload_ref,
            judge_scores=(
                {"score": 0.8, "judge_version": "j-2025-11", "rubric_version": "r2"},
            ),
        )
        assert run.judge_scores[0].judge_version == "j-2025-11"

    def test_bad_triple_inside_run_rejected(self, payload_ref):
        with pytest.raises(ValidationError):
            Run(
                task_id="t1",
                tenant_id="acme",
                status="failed",
                dag_spec_ref=payload_ref,
                judge_scores=({"score": 0.5},),
            )


class TestToolCall:
    def test_rejected_call_needs_no_result(self, payload_ref):
        tc = ToolCall(
            step_id="s1",
            tool_name="http.get",
            arguments_ref=payload_ref,
            status="rejected",
            latency_ms=2,
            error="schema violation",
        )
        assert tc.result_ref is None